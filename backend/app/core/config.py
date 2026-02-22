import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from backend directory
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(env_path)


class Settings:
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
    DB_USER: str = os.getenv("DB_USER", "root")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "root")
    DB_NAME: str = os.getenv("DB_NAME", "smart_truck")

    @property
    def DATABASE_URL(self) -> str:
        return f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"

    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    ML_SERVICE_URL: str = os.getenv("ML_SERVICE_URL", "http://localhost:8001")
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "../uploads")
    ML_MODELS_DIR: str = os.getenv("ML_MODELS_DIR", "../ml_models")

    # Data file paths for migration (configurable via .env)
    DATA_DIR: str = os.getenv("DATA_DIR", r"D:\Projects\excel_data_for_database_migration")
    TRIP_CSV_FILENAME: str = os.getenv("TRIP_CSV_FILENAME", "trip_data.csv")
    WAYPOINT_FILE_PATTERN: str = os.getenv("WAYPOINT_FILE_PATTERN", "Waypoint_*.xls")

    @property
    def TRIP_CSV_PATH(self) -> Path:
        return Path(self.DATA_DIR) / self.TRIP_CSV_FILENAME

    @property
    def WAYPOINT_DIR(self) -> Path:
        return Path(self.DATA_DIR)


settings = Settings()
