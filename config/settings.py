"""
Centralized settings for all Smart-Truck services.
Loads from .env at project root. Every service reads config from here.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (works regardless of which service imports this)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
_env_path = PROJECT_ROOT / ".env"
load_dotenv(_env_path)


class Settings:
    """Single source of truth for all configuration."""

    # --- Database ---
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
    DB_USER: str = os.getenv("DB_USER", "root")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "root")
    DB_NAME: str = os.getenv("DB_NAME", "smart_truck")

    @property
    def DB_CONFIG(self) -> dict:
        """PyMySQL-compatible connection kwargs."""
        return {
            "host": self.DB_HOST,
            "port": self.DB_PORT,
            "user": self.DB_USER,
            "password": self.DB_PASSWORD,
            "database": self.DB_NAME,
            "charset": "utf8mb4",
            "connect_timeout": 30,
            "read_timeout": 300,
            "write_timeout": 300,
        }

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )

    # --- API ---
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    ML_SERVICE_URL: str = os.getenv("ML_SERVICE_URL", "http://localhost:8001")
    ML_SERVICE_PORT: int = int(os.getenv("ML_SERVICE_PORT", "8001"))

    # --- Storage ---
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", str(PROJECT_ROOT / "uploads"))
    ML_MODELS_DIR: str = os.getenv("ML_MODELS_DIR", str(PROJECT_ROOT / "ml_models"))

    # --- Data migration ---
    DATA_DIR: str = os.getenv("DATA_DIR", r"D:\Projects\excel_data_for_database_migration")
    TRIP_CSV_FILENAME: str = os.getenv("TRIP_CSV_FILENAME", "trip_data.csv")
    WAYPOINT_FILE_PATTERN: str = os.getenv("WAYPOINT_FILE_PATTERN", "Waypoint_*.xls")

    @property
    def TRIP_CSV_PATH(self) -> Path:
        return Path(self.DATA_DIR) / self.TRIP_CSV_FILENAME

    @property
    def WAYPOINT_DIR(self) -> Path:
        return Path(self.DATA_DIR)

    # --- Logging ---
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = os.getenv(
        "LOG_FORMAT",
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # --- Misc ---
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    @property
    def PROJECT_ROOT(self) -> Path:
        return PROJECT_ROOT


settings = Settings()
