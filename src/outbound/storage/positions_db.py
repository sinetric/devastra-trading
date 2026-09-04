"""
SQLite-backed trade ledger — every filled buy becomes one row here, and the
exit scan in main.py updates a row in place when it closes.

Deliberately tracked in git (see the note next to trades.db in .gitignore):
for a hackathon, the actual trade history is part of the deliverable, not
disposable state like the parquet cache or logs.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from datetime import datetime

from src.outbound.models import Position, option_type as OptionType, Candidate_Result, parse_occ_symbol

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DB_PATH = PROJECT_ROOT / "trades.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_symbol TEXT NOT NULL,
    underlying_symbol TEXT NOT NULL,
    option_type TEXT NOT NULL,
    strike_price REAL NOT NULL,
    expiration_date TEXT NOT NULL,
    qty INTEGER NOT NULL,
    entry_premium REAL NOT NULL,
    entry_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    exit_premium REAL,
    exit_date TEXT,
    exit_reason TEXT
);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(_SCHEMA)
    return conn


def record_purchase(candidate: Candidate_Result, qty: int) -> int:
    """
    Insert a new open position from a filled buy. Expiration date is
    decoded straight from the OCC contract symbol rather than approximated
    from days_to_expiry, so it stays exact as time passes.

    Returns the new row's id (needed later to close_position() this exact
    lot, since the same contract_symbol can in principle be bought more
    than once).
    """
    decoded = parse_occ_symbol(candidate.contract_symbol)
    now = datetime.utcnow()

    conn = _connect()
    try:
        cur = conn.execute(
            """
            INSERT INTO positions (
                contract_symbol, underlying_symbol, option_type, strike_price,
                expiration_date, qty, entry_premium, entry_date, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open')
            """,
            (
                candidate.contract_symbol,
                candidate.underlying_symbol,
                candidate.option_type.value,
                candidate.strike_price,
                decoded.expiration_date.isoformat(),
                qty,
                candidate.premium,
                now.isoformat(),
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_open_positions() -> list[tuple[int, Position]]:
    """
    All currently-open rows, as (row_id, Position) pairs. The row id is
    handed back alongside the typed Position (rather than folded into it)
    because Position is the shape exit_strategy.evaluate_exit() expects,
    and it has no id field of its own — the id is only needed here, to
    know which row to update via close_position().
    """
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT id, contract_symbol, underlying_symbol, option_type, strike_price,
                   expiration_date, qty, entry_premium, entry_date
            FROM positions WHERE status = 'open'
            """
        ).fetchall()
    finally:
        conn.close()

    positions: list[tuple[int, Position]] = []
    for row in rows:
        (row_id, contract_symbol, underlying_symbol, opt_type_str, strike_price,
         expiration_date, qty, entry_premium, entry_date) = row

        positions.append((row_id, Position(
            contract_symbol=contract_symbol,
            underlying_symbol=underlying_symbol,
            option_type=OptionType(opt_type_str),
            strike_price=strike_price,
            expiration_date=datetime.fromisoformat(expiration_date),
            qty=qty,
            entry_premium=entry_premium,
            entry_date=datetime.fromisoformat(entry_date),
        )))

    return positions


def close_position(row_id: int, exit_premium: float, reasons: list[str]) -> None:
    """Mark a row closed with its exit premium, timestamp, and triggered reason(s)."""
    conn = _connect()
    try:
        conn.execute(
            """
            UPDATE positions
            SET status = 'closed', exit_premium = ?, exit_date = ?, exit_reason = ?
            WHERE id = ?
            """,
            (exit_premium, datetime.utcnow().isoformat(), "; ".join(reasons), row_id),
        )
        conn.commit()
    finally:
        conn.close()
