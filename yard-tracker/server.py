#!/usr/bin/env python3
"""Yard Helper tracker — no dependencies, just Python 3.

Run:  python3 server.py
Then open http://localhost:8765
"""
import hashlib
import hmac
import json
import os
import sqlite3
import datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).parent
DB_PATH = Path(os.environ.get("DB_PATH", ROOT / "yard.db"))
PORT = int(os.environ.get("PORT", 8765))
# If APP_PASSWORD is set, every page/API call requires the auth cookie.
# Leave it unset for open local development.
APP_PASSWORD = os.environ.get("APP_PASSWORD", "")


def auth_token():
    return hmac.new(APP_PASSWORD.encode(), b"yard-helper-auth-v1",
                    hashlib.sha256).hexdigest()

SEED_TASKS = [
    # (yard, phase, title, detail)
    ("front", "Phase 1 — Now through September (recovery)",
     "Start deep watering (cycle-and-soak)",
     "Run each zone ~15 min, wait an hour, repeat (ideally 3rd cycle). Target 1–1.5\"/week in 2 deep waterings. Check Burleson watering restrictions. Cracks should close in 2–3 weeks."),
    ("front", "Phase 1 — Now through September (recovery)",
     "Broadcast fire ant bait over whole yard",
     "Amdro or similar, whole yard — not just the mounds. Do before working the soil."),
    ("front", "Phase 1 — Now through September (recovery)",
     "First fertilizer application",
     "Only after ~2 weeks of consistent watering. Slow-release nitrogen (21-0-0 or 3-1-2 ratio) at ~1/2 lb N per 1,000 sq ft. Never fertilize dry bermuda in this heat."),
    ("front", "Phase 1 — Now through September (recovery)",
     "Second fertilizer application (early September)",
     "Same rate, ~6 weeks after the first."),
    ("front", "Phase 1 — Now through September (recovery)",
     "Start weekly mowing at 1.5–2\"",
     "Frequent mowing makes bermuda spread sideways. Leave the clippings."),
    ("front", "Phase 1 — Now through September (recovery)",
     "Spot-treat weeds (hand-pull or spot-spray only)",
     "Pull bitterweed and spurge after watering; spot-spray broadleaf weeds with a bermuda-safe product on a sub-90° morning. Ignore crabgrass this year — frost kills it."),
    ("front", "Phase 2 — Fall (September–October)",
     "Core-aerate (early September)",
     "Water the day before, two passes with a rented core aerator. Best fix for compacted clay."),
    ("front", "Phase 2 — Fall (September–October)",
     "Top-dress with 1/4\" compost after aerating (optional)",
     "Works into the aeration holes and builds organic matter into the clay."),
    ("front", "Phase 2 — Fall (September–October)",
     "Fall pre-emergent (mid-September)",
     "Prodiamine (e.g. Barricade) to block winter weeds."),
    ("front", "Phase 2 — Fall (September–October)",
     "Mail in soil test (Texas A&M AgriLife lab)",
     "$12–15 mail-in. Tells you exactly what to add and what to skip."),
    ("front", "Phase 3 — Next spring (March–June)",
     "Spring pre-emergent (early March)",
     "This is what actually beats crabgrass."),
    ("front", "Phase 3 — Next spring (March–June)",
     "Resume monthly fertilizer once nights stay above 65°",
     "1/2–1 lb N per 1,000 sq ft roughly monthly through summer. Keep deep watering and weekly mowing."),
    ("front", "Phase 3 — Next spring (March–June)",
     "Plug or sod any bare patches left by May",
     "Plug with pieces of backyard bermuda or a few pieces of sod — it knits fast."),

    ("back", "Putting green build",
     "Mark layout with a garden hose",
     "Kidney/organic shape hides seams. Practical size: 10'×15' to 12'×20'. Use the flattest part of the section."),
    ("back", "Putting green build",
     "Spray footprint with glyphosate",
     "Bermuda dies fast in summer heat. Wait a week before stripping."),
    ("back", "Putting green build",
     "Strip top 3–4\" of sod/soil",
     "Rent a sod cutter to make this fast."),
    ("back", "Putting green build",
     "Install perimeter edging",
     "Bender board or steel edging to contain the base."),
    ("back", "Putting green build",
     "Build and compact the base (3–4\" decomposed granite)",
     "Moisten, compact with rented plate compactor, screed smooth with a 2×4 and level. Slight crown or ~1% slope for drainage. Don't skimp — this determines putt quality and prevents heaving on clay."),
    ("back", "Putting green build",
     "Buy putting green turf",
     "Dedicated putting pile (~1/2\" nylon or polypropylene), NOT regular landscape turf. SGC, Purchase Green, or DFW-local suppliers. ~$3–6/sq ft."),
    ("back", "Putting green build",
     "Set 2–3 regulation 4\" cups",
     "Cut turf over each spot, set cup sleeves into compacted base flush with the surface."),
    ("back", "Putting green build",
     "Install turf",
     "Stretch, trim to edging, secure with 5–6\" non-galvanized nails every ~6\" around the perimeter."),
    ("back", "Putting green build",
     "Sand infill, broom in, and roll",
     "Thin layer of dry silica sand. More sand + rolling = faster green speed."),
    ("back", "Putting green build",
     "Add fringe turf strip (optional)",
     "Taller turf around the edge so you can chip onto the green."),
]


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            yard TEXT NOT NULL,
            phase TEXT NOT NULL,
            title TEXT NOT NULL,
            detail TEXT NOT NULL DEFAULT '',
            sort INTEGER NOT NULL,
            done INTEGER NOT NULL DEFAULT 0,
            done_date TEXT
        );
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            yard TEXT NOT NULL,
            date TEXT NOT NULL,
            note TEXT NOT NULL
        );
        """
    )
    if conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 0:
        for i, (yard, phase, title, detail) in enumerate(SEED_TASKS):
            conn.execute(
                "INSERT INTO tasks (yard, phase, title, detail, sort) VALUES (?,?,?,?,?)",
                (yard, phase, title, detail, i),
            )
    conn.commit()
    conn.close()


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _file(self, name, ctype):
        path = ROOT / name
        if not path.exists():
            self._send(404, {"error": "not found"})
            return
        self._send(200, path.read_bytes(), ctype)

    def _authed(self):
        if not APP_PASSWORD:
            return True
        for part in self.headers.get("Cookie", "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == "yard_auth" and hmac.compare_digest(v, auth_token()):
                return True
        return False

    def do_GET(self):
        url = urlparse(self.path)
        q = parse_qs(url.query)
        route = url.path
        if route == "/login":
            self._file("login.html", "text/html; charset=utf-8")
            return
        if route == "/styles.css":
            self._file("styles.css", "text/css")
            return
        if not self._authed():
            if route.startswith("/api/"):
                self._send(401, {"error": "unauthorized"})
            else:
                self.send_response(302)
                self.send_header("Location", "/login")
                self.end_headers()
            return
        if route == "/":
            self.send_response(302)
            self.send_header("Location", "/front")
            self.end_headers()
        elif route == "/front":
            self._file("front.html", "text/html; charset=utf-8")
        elif route == "/back":
            self._file("back.html", "text/html; charset=utf-8")
        elif route == "/watering":
            self._file("watering.html", "text/html; charset=utf-8")
        elif route == "/app.js":
            self._file("app.js", "text/javascript")
        elif route == "/api/tasks":
            yard = q.get("yard", ["front"])[0]
            conn = db()
            rows = [dict(r) for r in conn.execute(
                "SELECT * FROM tasks WHERE yard=? ORDER BY sort", (yard,))]
            conn.close()
            self._send(200, rows)
        elif route == "/api/logs":
            yard = q.get("yard", ["front"])[0]
            conn = db()
            rows = [dict(r) for r in conn.execute(
                "SELECT * FROM logs WHERE yard=? ORDER BY date DESC, id DESC", (yard,))]
            conn.close()
            self._send(200, rows)
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        route = urlparse(self.path).path
        if route == "/api/login":
            if APP_PASSWORD and hmac.compare_digest(
                    body.get("password", ""), APP_PASSWORD):
                data = json.dumps({"ok": True}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.send_header(
                    "Set-Cookie",
                    f"yard_auth={auth_token()}; Path=/; Max-Age=31536000; "
                    "HttpOnly; SameSite=Lax")
                self.end_headers()
                self.wfile.write(data)
            else:
                self._send(401, {"error": "wrong password"})
            return
        if not self._authed():
            self._send(401, {"error": "unauthorized"})
            return
        conn = db()
        if route == "/api/toggle":
            row = conn.execute("SELECT done FROM tasks WHERE id=?", (body["id"],)).fetchone()
            if row is None:
                conn.close()
                self._send(404, {"error": "no such task"})
                return
            done = 0 if row["done"] else 1
            done_date = datetime.date.today().isoformat() if done else None
            conn.execute("UPDATE tasks SET done=?, done_date=? WHERE id=?",
                         (done, done_date, body["id"]))
            conn.commit()
            conn.close()
            self._send(200, {"done": done, "done_date": done_date})
        elif route == "/api/logs":
            date = body.get("date") or datetime.date.today().isoformat()
            note = (body.get("note") or "").strip()
            yard = body.get("yard")
            if not note or yard not in ("front", "back"):
                conn.close()
                self._send(400, {"error": "need yard and note"})
                return
            cur = conn.execute("INSERT INTO logs (yard, date, note) VALUES (?,?,?)",
                               (yard, date, note))
            conn.commit()
            conn.close()
            self._send(200, {"id": cur.lastrowid, "date": date})
        elif route == "/api/logs/delete":
            conn.execute("DELETE FROM logs WHERE id=?", (body["id"],))
            conn.commit()
            conn.close()
            self._send(200, {"ok": True})
        else:
            conn.close()
            self._send(404, {"error": "not found"})

    def log_message(self, fmt, *args):
        pass  # keep the terminal quiet


if __name__ == "__main__":
    init_db()
    server = ThreadingHTTPServer(("", PORT), Handler)
    print(f"Yard Helper running →  http://localhost:{PORT}")
    print("  Front yard: http://localhost:%d/front" % PORT)
    print("  Backyard:   http://localhost:%d/back" % PORT)
    print("Ctrl+C to stop. Data lives in yard.db next to this file.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
