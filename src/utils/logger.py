"""
Simple per-execution logger. Each time the program runs, a new timestamped
log file is created under `logs/` at the project root, and every call to
log() writes a timestamped line to both that file and the console.

Usage:
    from src.utils import logger

    logger.log("bot started")
    logger.log("order rejected", level="warning")
    logger.log(f"unexpected response: {resp.text}", level="error")
"""

import logging
from datetime import datetime
from pathlib import Path

# project root is 3 levels up from this file (utils/ -> src/ -> root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
LOG_DIR = PROJECT_ROOT / "logs"
try:
    LOG_DIR.mkdir(exist_ok=True)
except OSError:
    # Deployed serverless environments (Vercel included) ship a read-only
    # filesystem everywhere except /tmp — fall back there instead of
    # crashing on import (which nearly every module in this project does,
    # via `from src.utils import logger`).
    import tempfile
    LOG_DIR = Path(tempfile.gettempdir()) / "devastra_logs"
    LOG_DIR.mkdir(exist_ok=True, parents=True)

# one log file per execution, named by the moment the process started
_RUN_TIMESTAMP = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
_LOG_FILE = LOG_DIR / f"run_{_RUN_TIMESTAMP}.log"

_logger = logging.getLogger("devastra_trading")
_logger.setLevel(logging.DEBUG)

# guard against duplicate handlers if this module gets imported more than once
if not _logger.handlers:
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(_LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)
    _logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    _logger.addHandler(console_handler)


def log(msg, level: str = "info") -> None:
    """
    Write `msg` to this execution's log file and the console, timestamped.

    level: "debug" | "info" | "warning" | "error" | "critical" (case-insensitive).
    Falls back to "info" if an unrecognized level is passed.
    """
    log_fn = getattr(_logger, level.lower(), None) or _logger.info
    log_fn(msg)


def get_log_file_path() -> Path:
    """Return the Path to the log file for this execution."""
    return _LOG_FILE
