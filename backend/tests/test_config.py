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


def test_empty_watch_folders_returns_empty_list():
    settings = Settings(watch_folders="")
    assert settings.watch_folder_paths == []


def test_watch_folders_trims_spaces_and_ignores_empty_segments(tmp_path: Path):
    first = tmp_path / "photos"
    second = tmp_path / "screenshots"

    settings = Settings(
        watch_folders=f"  {first}  , ,  {second}  ",
    )

    assert settings.watch_folder_paths == [first, second]
