import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SystemBrowserInfo:
    name: str
    executable: Path
    channel: str


def detect_system_browser() -> SystemBrowserInfo | None:
    """Locate an installed Chromium-based browser (Google Chrome or Microsoft Edge)."""
    if sys.platform == "darwin":
        candidates = [
            (
                "Google Chrome",
                Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
                "chrome",
            ),
            (
                "Microsoft Edge",
                Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
                "msedge",
            ),
            (
                "Google Chrome Beta",
                Path(
                    "/Applications/Google Chrome Beta.app/Contents/MacOS/Google Chrome Beta"
                ),
                "chrome-beta",
            ),
            (
                "Google Chrome User",
                Path.home()
                / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                "chrome",
            ),
        ]
        for name, path, channel in candidates:
            if path.is_file() and os.access(path, os.X_OK):
                return SystemBrowserInfo(name=name, executable=path, channel=channel)
        return None
    elif sys.platform == "win32":
        prefixes: list[Path] = []
        for env_var in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
            val = os.environ.get(env_var)
            if val:
                prefixes.append(Path(val))

        win_candidates = [
            ("Google Chrome", Path("Google/Chrome/Application/chrome.exe"), "chrome"),
            ("Microsoft Edge", Path("Microsoft/Edge/Application/msedge.exe"), "msedge"),
        ]
        for prefix in prefixes:
            for name, subpath, channel in win_candidates:
                exe = prefix / subpath
                if exe.is_file():
                    return SystemBrowserInfo(name=name, executable=exe, channel=channel)
        return None
    else:
        # Linux
        linux_candidates = [
            ("google-chrome", "chrome"),
            ("google-chrome-stable", "chrome"),
            ("microsoft-edge", "msedge"),
            ("microsoft-edge-stable", "msedge"),
            ("chromium", "chromium"),
            ("chromium-browser", "chromium"),
        ]
        for binary, channel in linux_candidates:
            found = shutil.which(binary)
            if found:
                return SystemBrowserInfo(
                    name=binary,
                    executable=Path(found),
                    channel=channel,
                )
        return None
