"""
Standalone utility to delete all log files under logs/, with a confirmation
prompt first. Not part of the bot's runtime — run it directly when you want
to clean up:

    python -m src.utils.clear_logs
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
LOG_DIR = PROJECT_ROOT / "logs"


def clear_logs(skip_confirmation: bool = False) -> None:
    if not LOG_DIR.exists():
        print("No logs/ directory found — nothing to clear.")
        return

    log_files = sorted(LOG_DIR.glob("*.log"))

    if not log_files:
        print("No log files found — nothing to clear.")
        return

    print(f"Found {len(log_files)} log file(s) in {LOG_DIR}:")
    for f in log_files:
        print(f"  - {f.name}")

    if not skip_confirmation:
        answer = input(f"\nDelete all {len(log_files)} log file(s)? [y/N]: ").strip().lower()
        if answer != "y":
            print("Cancelled — no files deleted.")
            return

    deleted = 0
    for f in log_files:
        f.unlink()
        deleted += 1

    print(f"Deleted {deleted} log file(s).")


if __name__ == "__main__":
    clear_logs()
