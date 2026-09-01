from pathlib import Path

from PyInstaller.__main__ import run  # type: ignore[import-untyped]

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DESKTOP_BUILD = _PROJECT_ROOT / "desktop" / "build"


def main() -> None:
    run(
        [
            "--noconfirm",
            "--clean",
            "--onedir",
            "--name",
            "asagent-backend",
            "--distpath",
            str(_DESKTOP_BUILD / "dist"),
            "--workpath",
            str(_DESKTOP_BUILD / "work"),
            "--specpath",
            str(_DESKTOP_BUILD / "spec"),
            "--paths",
            str(_PROJECT_ROOT / "src"),
            "--hidden-import",
            "aiosqlite",
            "--add-data",
            f"{_PROJECT_ROOT / 'alembic.ini'}:.",
            "--add-data",
            f"{_PROJECT_ROOT / 'alembic'}:alembic",
            "--add-data",
            f"{_PROJECT_ROOT / 'app-assets' / 'models'}:app-assets/models",
            str(_PROJECT_ROOT / "src" / "asagent" / "cli.py"),
        ],
    )


if __name__ == "__main__":
    main()
