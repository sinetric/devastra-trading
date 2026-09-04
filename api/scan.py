"""
Vercel entrypoint — one scan cycle per invocation, triggered by the cron
schedule in vercel.json (or manually via a GET request to /api/scan).

This is NOT the same thing as running src/main.py's run() loop: there is
no `while True` here and no in-process sleep between cycles. Vercel
functions are stateless and short-lived — this file runs scan_and_trade()
+ evaluate_exits() exactly once per invocation and returns, and the cron
schedule is what provides the "keep checking" behavior instead of an
in-process loop. State that needs to survive between invocations (open
positions) lives in Postgres via DATABASE_URL — see
src/outbound/storage/positions_db.py's module docstring for why SQLite
doesn't work here.

Required environment variables (set these in the Vercel project's
Settings -> Environment Variables — this file can't set them for you):
    APCA_API_KEY_ID, APCA_API_SECRET_KEY  — Alpaca paper trading credentials
    DATABASE_URL                          — any Postgres connection string
"""

import sys
import os
import json
import traceback
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.main import scan_and_trade, evaluate_exits
from config.settings import get_settings


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        settings = get_settings()
        result = {"ok": True, "errors": []}

        try:
            scan_and_trade(settings)
        except Exception as e:
            result["ok"] = False
            result["errors"].append({"stage": "scan_and_trade", "error": str(e), "trace": traceback.format_exc()})

        try:
            evaluate_exits(settings)
        except Exception as e:
            result["ok"] = False
            result["errors"].append({"stage": "evaluate_exits", "error": str(e), "trace": traceback.format_exc()})

        body = json.dumps(result, default=str).encode()
        self.send_response(200 if result["ok"] else 500)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)
