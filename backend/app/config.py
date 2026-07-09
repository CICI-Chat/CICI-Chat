from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", populate_by_name=True
    )

    watch_folders: str = Field(default="", alias="WATCH_FOLDERS")
    db_path: Path = Field(default=Path("./data/picmind.db"), alias="DB_PATH")
    recognition_provider: str = Field(default="mock", alias="RECOGNITION_PROVIDER")
    yolo_model_path: Path = Field(
        default=Path("D:/my vibe coding/models/yolo/yolo11n.pt"),
        alias="YOLO_MODEL_PATH",
    )
    yolo_confidence_threshold: float = Field(default=0.25, alias="YOLO_CONFIDENCE_THRESHOLD")
    camera_source: str = Field(default="0", alias="CAMERA_SOURCE")

    @property
    def camera_device(self) -> int | str:
        """摄像头来源：纯数字返回 int（USB），否则返回字符串（网络流 URL）。"""
        s = self.camera_source.strip()
        return int(s) if s.isdigit() else s

    @property
    def watch_folder_paths(self) -> list[Path]:
        if not self.watch_folders.strip():
            return []
        return [Path(value.strip()) for value in self.watch_folders.split(",") if value.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
