import collections, json, os, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from dotenv import load_dotenv
load_dotenv()  # read .env if present
from typesafe_sdk import Choice, TypeSafeClient

ROOT = Path(__file__).parent
PER_SEC, PER_MIN = int(os.environ.get("RATE_PER_SEC", 12)), int(os.environ.get("RATE_PER_MIN", 400))
DAILY_CAP = int(os.environ.get("DAILY_CAP", 30000))
GAME = "side-scrolling runner; a 40px cube auto-runs right along the ground and its only action is jump"
KINDS = {"spikes", "block", "mixed"}
QUESTIONS = {
    "action": Choice(
        instructions=(
            "You control a 40px cube in a side-scrolling runner. It auto-runs right along the ground and its only "
            "action is jump (max height 129px). Decide what to do about next_obstacle. Any spike, or any block, "
            "hits the cube unless it jumps."
        ),
        criteria={
            "jump": "next_obstacle is in the cube's path and will hit it unless the cube jumps over or onto it.",
            "run": "There is no obstacle that needs clearing.",
        },
    )
}
client = TypeSafeClient() if os.environ.get("TYPESAFE_API_KEY") else None  # reads the key from the environment
hits, day, lock = collections.defaultdict(collections.deque), {"d": None, "n": 0}, threading.Lock()


def allow(ip):
    now = time.time()
    with lock:
        q = hits[ip]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= PER_MIN or sum(1 for t in q if now - t < 1) >= PER_SEC:
            return "rate limited"
        today = time.strftime("%Y-%m-%d", time.gmtime())
        if day["d"] != today:
            day.update(d=today, n=0)
            hits.clear()
        if day["n"] >= DAILY_CAP:
            return "daily budget reached"
        q.append(now)
        day["n"] += 1
    return None


def num(v, lo, hi):
    v = float(v)
    if not lo <= v <= hi:
        raise ValueError("out of range")
    return round(v, 2)


def obstacle(o):
    if o["kind"] not in KINDS:
        raise ValueError("bad kind")
    return {"kind": o["kind"], "width_px": num(o["width_px"], 1, 900), "height_px": num(o["height_px"], 1, 200),
            "seconds_until_contact": num(o["seconds_until_contact"], -2, 10)}


def build_state(d):  # rebuild from validated numbers only; nothing user-written is forwarded
    return {"game": GAME, "cube_size_px": 40, "jump_max_height_px": 129, "speed_px_s": num(d["speed_px_s"], 100, 1200),
            "next_obstacle": obstacle(d["next_obstacle"]), "following": [obstacle(x) for x in list(d.get("following", []))[:2]]}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _ip(self):
        if os.environ.get("TRUST_PROXY"):  # only set behind a proxy you control (Render, Fly, nginx...)
            return self.headers.get("X-Forwarded-For", self.client_address[0]).split(",")[0].strip()
        return self.client_address[0]

    def do_GET(self):
        if self.path == "/api/status":
            return self._send(200, {"ready": client is not None, "reason": "" if client else "Jev is not configured on this server"})
        if self.path in ("/", "/index.html"):
            return self._send(200, (ROOT / "index.html").read_bytes(), "text/html; charset=utf-8")
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/api/decide":
            return self._send(404, {"error": "not found"})
        origin = self.headers.get("Origin")
        if origin and urlparse(origin).netloc != self.headers.get("Host"):
            return self._send(403, {"error": "forbidden origin"})
        if client is None:
            return self._send(503, {"error": "Jev not configured"})
        why = allow(self._ip())
        if why:
            return self._send(429, {"error": why})
        try:
            n = int(self.headers.get("Content-Length", 0))
            if not 0 < n <= 2000:
                raise ValueError("bad size")
            state = build_state(json.loads(self.rfile.read(n)))
            ans = client.system_one(state=state, questions=QUESTIONS).answers["action"]
            conf = getattr(ans, "confidence", None)
            self._send(200, {"action": ans.choice, "confidence": float(conf) if isinstance(conf, (int, float)) else None})
        except (ValueError, KeyError, TypeError):
            self._send(400, {"error": "bad request"})
        except Exception:  # upstream/API failure: don't leak details to the public
            self._send(502, {"error": "Jev unavailable"})

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    host, port = os.environ.get("HOST", "127.0.0.1"), int(os.environ.get("PORT", 8000))
    print(f"NEON DASH -> http://{host}:{port}  |  Jev:", "ready" if client else "no TYPESAFE_API_KEY set")
    ThreadingHTTPServer((host, port), Handler).serve_forever()