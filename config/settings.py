"""Central configuration for the Data Engineering pipeline.

All environment-specific values (database credentials, paths) are read
from environment variables, loaded from a local `.env` file in
development via python-dotenv. Nothing sensitive is hardcoded here —
see `.env.example` for the variables this module expects.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DATA_CURATED_DIR = PROJECT_ROOT / "data" / "curated"
DATA_REJECTED_DIR = PROJECT_ROOT / "data" / "rejected"
DATA_VALIDATED_DIR = PROJECT_ROOT / "data" / "validated"
DATA_WAREHOUSE_DIR = PROJECT_ROOT / "data" / "warehouse"


@dataclass(frozen=True)
class PostgresSettings:
    host: str = os.getenv("POSTGRES_HOST", "localhost")
    port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    database: str = os.getenv("POSTGRES_DB", "dataeng_warehouse")
    user: str = os.getenv("POSTGRES_USER", "postgres")
    password: str = os.getenv("POSTGRES_PASSWORD", "")

    @property
    def sqlalchemy_url(self) -> str:
        # user/password are URL-encoded: a password containing '@', ':', or
        # '/' (all valid in a real password) would otherwise be misparsed
        # as part of the host/path when substituted into the DSN directly.
        return (
            f"postgresql+psycopg2://{quote_plus(self.user)}:{quote_plus(self.password)}"
            f"@{self.host}:{self.port}/{self.database}"
        )


postgres = PostgresSettings()
