import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


class ChromeCdpLauncher:
    """Manages the child process of a debugging-enabled system Chrome/Edge instance."""

    def __init__(
        self,
        executable: Path,
        user_data_dir: Path,
        *,
        headless: bool = False,
        extra_args: list[str] | None = None,
    ) -> None:
        self._executable = executable
        self._user_data_dir = user_data_dir
        self._headless = headless
        self._extra_args = extra_args or []
        self._proc: subprocess.Popen[bytes] | None = None
        self._port: int | None = None

    @property
    def endpoint(self) -> str:
        """CDP HTTP endpoint (valid after a successful launch)."""
        return f"http://127.0.0.1:{self._port}" if self._port else ""

    @property
    def port(self) -> int | None:
        return self._port

    @staticmethod
    def _find_free_port() -> int:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(("127.0.0.1", 0))
            return int(s.getsockname()[1])
        finally:
            s.close()

    def _clear_stale_profile(self) -> None:
        """Remove stale process locks and incomplete WAL journals from crashes.

        The automation profile is a **persistent** directory: it retains
        cookies, local-storage and login sessions across runs so the user
        only needs to log in once.  We must *not* wipe the entire directory.

        What we *do* remove:
        - Process-level lock files (SingletonLock/Socket/Cookie) — these are
          only valid while Chrome is running; leftover locks from a crash
          prevent the next launch.
        - SQLite WAL journal files (*-journal / *-wal) — incomplete journals
          from an unclean shutdown cause Chrome to detect "profile corruption"
          and show the error dialog.  Removing them lets Chrome rebuild the
          indexes on next start without losing the main database files.
        """
        if not self._user_data_dir.exists():
            return

        # Root-level process locks
        for name in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
            p = self._user_data_dir / name
            try:
                if os.path.lexists(p):
                    os.remove(p)
            except OSError:
                pass

        # Per-profile WAL journals that trigger "profile corruption" dialog
        default_dir = self._user_data_dir / "Default"
        if default_dir.exists():
            for name in (
                "Web Data-journal",
                "Web Data-wal",
                "History-journal",
                "History-wal",
                "Cookies-journal",
                "Cookies-wal",
                "Favicons-journal",
                "Favicons-wal",
                "Login Data-journal",
                "Login Data-wal",
                "Shortcuts-journal",
                "Top Sites-journal",
            ):
                p = default_dir / name
                try:
                    if os.path.lexists(p):
                        os.remove(p)
                except OSError:
                    pass

    def launch(self, ready_timeout: float = 25.0) -> str:
        """Spawn Chrome and block until its CDP DevTools endpoint responds."""
        self._clear_stale_profile()
        self._user_data_dir.mkdir(parents=True, exist_ok=True)
        self._port = self._find_free_port()

        args = [
            str(self._executable),
            f"--remote-debugging-port={self._port}",
            f"--user-data-dir={self._user_data_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--noerrdialogs",
            "--disable-background-networking",
            "--disable-component-update",
            "--disable-sync",
            "--disable-default-apps",
            "--disable-infobars",
            "--password-store=basic",
            "--use-mock-keychain",
            "--hide-crash-restore-bubble",
            "--disable-features=Translate,OptimizationHints,MediaRouter",
            "about:blank",
        ]
        if self._headless:
            args.insert(1, "--headless=new")
        args[1:1] = self._extra_args

        # On macOS, Chrome uses Launch Services singleton detection.  Setting
        # a per-subprocess environment with CHROME_USER_DATA_DIR matching
        # --user-data-dir tells the child it *is* the primary instance for
        # that profile, preventing it from handing off to an already-running
        # personal Chrome instance (which would cause profile conflicts).
        child_env = os.environ.copy()
        child_env["CHROME_USER_DATA_DIR"] = str(self._user_data_dir)

        self._proc = subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=(sys.platform != "win32"),
            env=child_env,
        )

        if not self._wait_ready(ready_timeout):
            port = self._port
            self.close()
            raise RuntimeError(
                f"System browser did not expose a CDP endpoint on port {port} "
                f"within {ready_timeout:.0f}s"
            )
        return self.endpoint

    def _wait_ready(self, timeout: float) -> bool:
        deadline = time.time() + timeout
        url = f"http://127.0.0.1:{self._port}/json/version"
        while time.time() < deadline:
            if self._proc and self._proc.poll() is not None:
                return False
            try:
                with urllib.request.urlopen(url, timeout=1) as response:
                    if response.status == 200:
                        return True
            except Exception:
                time.sleep(0.15)
        return False

    def is_alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def close(self) -> None:
        """Gracefully terminate the Chrome process."""
        proc = self._proc
        self._proc = None
        self._port = None
        if proc is None:
            return
        if proc.poll() is not None:
            return
        try:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)
        except Exception:
            pass
