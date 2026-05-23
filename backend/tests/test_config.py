from pathlib import Path

from app.config import Settings


def test_settings_parses_watch_folders(tmp_path: Path):
    first = tmp_path / "photos"
    second = tmp_path / "screenshots"

    settings = Settings(
        watch_folders=f"{first},{second}",
        db_path=str(tmp_path / "picmind.db"),
    )

    assert settings.watch_folder_paths == [first, second]
    assert settings.db_path == tmp_path / "picmind.db"
