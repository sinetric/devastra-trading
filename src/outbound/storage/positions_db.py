"""
Trade ledger — every filled buy becomes one row here, and the exit scan
closes a row in place when it exits.

Two backends behind the same three functions (record_purchase/
get_open_positions/close_position), selected by whether DATABASE_URL is
set:

  - No DATABASE_URL (local/dev, e.g. running src/main.py yourself): SQLite
    at trades.db in the project root. Deliberately tracked in git (see the
    note next to it in .gitignore) — for a hackathon, trade history is
    part of the deliverable, not disposable state like the parquet cache.

  - DATABASE_URL set (Vercel deployment): Postgres. Vercel's serverless
    functions have an ephemeral filesystem — nothing written to disk
    survives between invocations — so the scan-on-a-cron-trigger version
    (api/scan.py) can't use SQLite at all; it needs a real external
    database to remember open positions between runs. Point DATABASE_URL
    at any Postgres instance (Vercel Postgres/Neon/Supabase all work).
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from datetime import datetime

from src.outbound.models import Position, option_type as OptionType, Candidate_Result, parse_occ_symbol

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DB_PATH = PROJECT_ROOT / "trades.db"

DATABASE_URL = os.getenv("DATABASE_URL")
_USE_POSTGRES = bool(DATABASE_URL)

_SCHEMA_SQLITE = """
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

_SCHEMA_POSTGRES = """
CREATE TABLE IF NOT EXISTS positions (
    id SERIAL PRIMARY KEY,
    contract_symbol TEXT NOT NULL,
    underlying_symbol TEXT NOT NULL,
    option_type TEXT NOT NULL,
    strike_price DOUBLE PRECISION NOT NULL,
    expiration_date TEXT NOT NULL,
    qty INTEGER NOT NULL,
    entry_premium DOUBLE PRECISION NOT NULL,
    entry_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    exit_premium DOUBLE PRECISION,
    exit_date TEXT,
    exit_reason TEXT
);
"""


def _connect():
    """
    Returns a DB-API connection with schema ensured. Callers use `?`
    placeholders everywhere below — translated to Postgres's `%s` here so
    the query strings themselves don't need an if/else at every call site.
    """
    if _USE_POSTGRES:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        with conn.cursor() as cur:
            cur.execute(_SCHEMA_POSTGRES)
        conn.commit()
        return conn

    conn = sqlite3.connect(DB_PATH)
    conn.execute(_SCHEMA_SQLITE)
    return conn


def _execute(conn, query: str, params: tuple = ()):
    """Runs `query` (written with `?` placeholders) against either backend, returns the cursor."""
    if _USE_POSTGRES:
        query = query.replace("?", "%s")
        cur = conn.cursor()
        cur.execute(query, params)
        return cur

    return conn.execute(query, params)


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
        params = (
            candidate.contract_symbol,
            candidate.underlying_symbol,
            candidate.option_type.value,
            candidate.strike_price,
            decoded.expiration_date.isoformat(),
            qty,
            candidate.premium,
            now.isoformat(),
        )

        if _USE_POSTGRES:
            cur = _execute(
                conn,
                """
                INSERT INTO positions (
                    contract_symbol, underlying_symbol, option_type, strike_price,
                    expiration_date, qty, entry_premium, entry_date, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open')
                RETURNING id
                """,
                params,
            )
            row_id = cur.fetchone()[0]
        else:
            cur = _execute(
                conn,
                """
                INSERT INTO positions (
                    contract_symbol, underlying_symbol, option_type, strike_price,
                    expiration_date, qty, entry_premium, entry_date, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open')
                """,
                params,
            )
            row_id = cur.lastrowid

        conn.commit()
        return row_id
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
        cur = _execute(
            conn,
            """
            SELECT id, contract_symbol, underlying_symbol, option_type, strike_price,
                   expiration_date, qty, entry_premium, entry_date
            FROM positions WHERE status = 'open'
            """,
        )
        rows = cur.fetchall()
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
        _execute(
            conn,
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
