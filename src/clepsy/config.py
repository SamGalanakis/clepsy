import base64
import binascii
from datetime import timedelta
from importlib.metadata import version
import logging
import os
from pathlib import Path
import sys
from typing import Literal
import warnings

from loguru import logger
from pydantic import SecretBytes, SecretStr
from pydantic_settings import BaseSettings


warnings.filterwarnings("ignore", message="No ccache found")

logging.getLogger("urllib3").setLevel(logging.INFO)
logging.getLogger("PIL").setLevel(logging.INFO)
logging.getLogger("aiosqlite").setLevel(logging.INFO)
logging.getLogger("aiocache").setLevel(logging.INFO)
logging.getLogger("asyncio").setLevel(logging.INFO)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

logging.getLogger("dramatiq").setLevel(logging.INFO)
logging.getLogger("dramatiq.worker").setLevel(logging.INFO)
logging.getLogger("dramatiq.broker").setLevel(logging.INFO)
logging.getLogger("dramatiq.middleware").setLevel(logging.INFO)
logging.getLogger("dramatiq.message").setLevel(logging.INFO)
logging.getLogger("dramatiq.actor").setLevel(logging.INFO)

logging.getLogger("python_multipart.multipart").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)


loggers = (
    "uvicorn",
    "uvicorn.access",
    "uvicorn.error",
    "fastapi",
    "asyncio",
    "starlette",
)

for logger_name in loggers:
    logging_logger = logging.getLogger(logger_name)
    logging_logger.handlers = []
    logging_logger.propagate = True


def decode_key_file(data: bytes) -> bytes | None:
    try:
        text = data.decode().strip()
        lines = text.splitlines()
        if lines[0] != "CLEPSY-KEY":
            return None
        b64 = lines[1].strip()
        # pad if needed
        b64 += "=" * (-len(b64) % 4)
        return base64.b64decode(b64, validate=True)
    except (UnicodeDecodeError, binascii.Error, ValueError):
        logger.exception("Failed to decode key file")
        return None


def init_master_key(path: Path) -> bytes:
    if path.is_file():
        raw = path.read_bytes()
        k = decode_key_file(raw)
        if k is None or len(k) != 32:
            raise ValueError(f"Invalid key file: {path}")
        return k

    # create new key
    key = os.urandom(32)
    b64 = base64.b64encode(key).decode().rstrip("=")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"CLEPSY-KEY\n{b64}\n")

    return key


cache_dir = Path("/var/lib/clepsy-caches")


class Config(BaseSettings):
    log_file_path: Path = Path("/var/lib/clepsy/logs/app.log")
    master_key_file_path: Path = Path("/var/lib/clepsy/secret.key")
    master_key: SecretBytes = SecretBytes(init_master_key(master_key_file_path))
    aggregation_interval: timedelta = timedelta(minutes=10)  # 20
    aggregation_grace_period: timedelta = timedelta(minutes=1)
    db_path: Path = Path("/var/lib/clepsy/db.sqlite3")
    screenshot_max_size_vlm: tuple[int, int] = (1024, 1024)
    screenshot_max_size_ocr: tuple[int, int] = (1920, 1080)
    software_version: str = version("clepsy")
    bootstrap_password_file_path: Path = Path("/var/lib/clepsy/bootstrap_password.txt")
    bootstrap_password: SecretStr | None = None
    api_host: str = "0.0.0.0"
    max_desktop_screenshot_log_interval_seconds: int = 30
    api_port: int = int(os.environ["PORT"])
    cache_dir: Path = cache_dir
    jwt_secret: SecretStr = SecretStr(
        os.getenv("JWT_SECRET", binascii.hexlify(os.urandom(24)).decode())
    )
    jwt_algorithm: str = "HS256"
    environment: Literal["dev", "prod"]
    boundary_project_id: str | None = os.getenv("BOUNDARY_PROJECT_ID")
    boundary_secret: SecretStr | None = (
        SecretStr(os.environ["BOUNDARY_SECRET"])
        if os.getenv("BOUNDARY_SECRET")
        else None
    )
    max_activity_pause_time: timedelta = timedelta(minutes=5)
    source_enrollment_code_ttl: timedelta = timedelta(minutes=30)
    log_level: str | None = None

    max_session_gap: timedelta = timedelta(minutes=10)
    min_session_length: timedelta = timedelta(minutes=15)
    min_activities_per_session: int = 3
    min_session_purity: float = 0.8
    session_window_length: timedelta = timedelta(minutes=30)
    max_activities_per_session_llm_call: int = 100
    max_session_window_overlap: timedelta = timedelta(minutes=15)
    gliner_pii_model: str = "knowledgator/gliner-pii-small-v1.0"
    gliner_pii_threshold: float = 0.5
    gliner_cache_dir: Path = cache_dir / "gliner"
    valkey_url: str
    ap_scheduler_sqlite_db_path: Path = Path("/var/lib/clepsy/apscheduler.sqlite3")

    @property
    def ap_scheduler_db_connection_string(self) -> str:
        return f"sqlite:////{self.ap_scheduler_sqlite_db_path.as_posix()}"

    @property
    def is_dev(self) -> bool:
        return self.environment == "dev"

    @property
    def is_prod(self) -> bool:
        return self.environment == "prod"

    @property
    def max_pause_time_seconds(self) -> int:
        return int(self.max_activity_pause_time.total_seconds())

    @property
    def aggregation_interval_minutes(self) -> int:
        return int(self.aggregation_interval.total_seconds() // 60)


config = Config()  # type: ignore

if not config.log_level:
    config.log_level = "DEBUG" if config.is_dev else "INFO"


baml_log_level = os.environ.get("BAML_LOG")
if not baml_log_level:
    baml_log_level = "info" if config.is_dev else "warn"
    os.environ["BAML_LOG"] = baml_log_level


class InterceptHandler(logging.Handler):
    def emit(self, record):
        # Get corresponding Loguru level
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller to get correct stack depth
        frame, depth = logging.currentframe(), 2
        while frame.f_back and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

logger.remove(0)
logger.add(
    sys.stderr,
    level=config.log_level,
    backtrace=True,
    diagnose=False,
    enqueue=True,
)

config.log_file_path.parent.mkdir(exist_ok=True, parents=True)

logger.add(
    config.log_file_path.resolve(),
    rotation="50 MB",
    retention=timedelta(days=7),
    backtrace=True,
    diagnose=False,
    level=config.log_level,
    enqueue=True,
)


if not config.db_path.is_file():
    raise FileNotFoundError("Db file not found - migrations failed?")

config.cache_dir.mkdir(exist_ok=True, parents=True)

config.gliner_cache_dir.mkdir(exist_ok=True, parents=True)

logger.info(f"Running in {config.environment} mode")
