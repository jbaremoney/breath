# file: pi_bac_server.py
import socket, json, time, html, urllib.parse, os
from typing import Tuple, Dict, Any

HOST = "0.0.0.0"
PORT = 8080
STORE = "leaderboard.json"

# ---------------- State ----------------
leaderboard = []        # list[{"name": str, "bac": float, "ts": float}]
ready_until = 0.0       # epoch seconds while we're in "ready" state

def load_store():
    global leaderboard
    if os.path.exists(STORE):
        try:
            with open(STORE, "r") as f:
                leaderboard = json.load(f)
        except Exception:
            leaderboard = []

def save_store():
    tmp = STORE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(leaderboard, f)
    os.replace(tmp, STORE)

# ---------------- HTTP helpers ----------------
REASONS = {200:"OK", 201:"Created", 204:"No Content", 400:"Bad Request",
           404:"Not Found", 405:"Method Not Allowed", 413:"Payload Too Large"}

def http_response(status: int, headers: Dict[str,str], body: bytes=b"") -> bytes:
    reason = REASONS.get(status, "OK")
    head_lines = [f"HTTP/1.1 {status} {reason}"] + [f"{k}: {v}" for k,v in headers.items()] + ["", ""]
    return ("\r\n".join(head_lines)).encode("utf-8") + body

def read_http_request(conn) -> Tuple[str, str, Dict[str,str], bytes]:
    """
    Return (method, path, headers, body) for one HTTP/1.1 request.
    We read until \r\n\r\n (end of headers), then Content-Length bytes (if any).
    """
    conn.settimeout(5)
    buf = b""
    # Cap header size to avoid abuse
    while b"\r\n\r\n" not in buf:
        chunk = conn.recv(4096)
        if not chunk:
            break
        buf += chunk
        if len(buf) > 64 * 1024:
            raise ValueError("Headers too large")

    header_part, _, rest = buf.partition(b"\r\n\r\n")
    lines = header_part.decode("iso-8859-1").split("\r\n")
    if not lines:
        raise ValueError("Empty request")

    request_line = lines[0]
    parts = request_line.split(" ")
    if len(parts) < 2:
        raise ValueError("Bad request line")
    method = parts[0].upper()
    path = parts[1]

    headers: Dict[str,str] = {}
    for line in lines[1:]:
        if not line or ":" not in line:
            continue
        k, v = line.split(":", 1)
        headers[k.strip().lower()] = v.strip()

    body = rest
    content_length = int(headers.get("content-length", "0") or "0")
    if content_length > 0:
        # Read remaining body if not all arrived yet
        while len(body) < content_length:
            chunk = conn.recv(min(4096, content_length - len(body)))
            if not chunk:
                break
            body += chunk
        if len(body) > 2 * 1024 * 1024:  # 2MB safeguard
            raise ValueError("Body too large")

    return method, path, headers, body

def json_response(obj: Any, status=200):
    data = json.dumps(obj).encode("utf-8")
    return http_response(status, {
        "Content-Type": "application/json; charset=utf-8",
        "Content-Length": str(len(data)),
        "Connection": "close",
    }, data)

def html_response(s: str, status=200):
    data = s.encode("utf-8")
    return http_response(status, {
        "Content-Type": "text/html; charset=utf-8",
        "Content-Length": str(len(data)),
        "Connection": "close",
    }, data)

# ---------------- Routes ----------------
def route(method: str, path: str, headers: Dict[str,str], body: bytes) -> bytes:
    # Handle favicon noise gracefully
    if path == "/favicon.ico":
        return http_response(204, {"Connection": "close"})

    if method == "GET" and path == "/":
        return html_response(render_home())

    if method == "GET" and path == "/api/leaderboard":
        return json_response(sorted_leaderboard(20))

    if method == "POST" and path == "/api/reading":
        try:
            ct = headers.get("content-type", "")
            if "application/json" in ct:
                payload = json.loads(body.decode("utf-8") or "{}")
            elif "application/x-www-form-urlencoded" in ct:
                payload = {k:v[0] for k,v in urllib.parse.parse_qs(body.decode("utf-8")).items()}
            else:
                # Best effort: try JSON, then form
                try:
                    payload = json.loads(body.decode("utf-8") or "{}")
                except Exception:
                    payload = {k:v[0] for k,v in urllib.parse.parse_qs(body.decode("utf-8")).items()}

            name = (payload.get("name") or "Anonymous").strip()
            bac = float(payload.get("bac"))
            # sanity clamp (BAC in % e.g. 0.08 for 0.08%)
            bac = max(0.0, min(bac, 0.5))

            leaderboard.append({"name": name[:40], "bac": round(bac, 4), "ts": time.time()})
            # Keep only top N by BAC to bound file size
            leaderboard.sort(key=lambda r: (-r["bac"], r["ts"]))
            del leaderboard[200:]
            save_store()
            return json_response({"ok": True}, status=201)
        except Exception as e:
            return json_response({"ok": False, "error": str(e)}, status=400)

    if method == "POST" and path == "/api/ready":
        set_breathalyzer_ready(20)  # 20 seconds "ready" window
        return json_response({"ok": True, "ready_for_secs": max(0, int(ready_until - time.time()))})

    # Method fallbacks
    if method in ("GET","POST"):
        return http_response(404, {"Connection":"close", "Content-Type":"text/plain"}, b"Not Found")
    else:
        return http_response(405, {"Connection":"close", "Allow":"GET, POST"})

# ---------------- UI ----------------
def sorted_leaderboard(limit=10):
    return [{"rank": i+1, "name": r["name"], "bac": r["bac"], "ts": r["ts"]}
            for i, r in enumerate(sorted(leaderboard, key=lambda r: (-r["bac"], r["ts"]))[:limit])]

def render_home() -> str:
    rows = []
    for item in sorted_leaderboard(10):
        t = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(item["ts"]))
        rows.append(
            f"<tr><td>{item['rank']}</td><td>{html.escape(item['name'])}</td>"
            f"<td>{item['bac']:.3f}</td><td>{t}</td></tr>"
        )
    ready_badge = ("<span style='padding:4px 8px;border-radius:8px;background:#d1fae5'>READY</span>"
                   if time.time() < ready_until else
                   "<span style='padding:4px 8px;border-radius:8px;background:#fee2e2'>IDLE</span>")
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>Breathalyzer Leaderboard</title>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 24px; }}
    table {{ border-collapse: collapse; width: 100%; max-width: 800px; }}
    th, td {{ border-bottom: 1px solid #eee; padding: 8px 10px; text-align: left; }}
    th {{ background: #fafafa; }}
    .bar {{ display:flex; gap:12px; align-items:center; margin: 12px 0 24px; }}
    button {{ padding: 8px 12px; border: 0; border-radius: 8px; cursor: pointer; }}
    #msg {{ margin-left: 8px; opacity: 0.8; }}
    form {{ margin-top: 24px; display:flex; gap:8px; flex-wrap:wrap; align-items: baseline; }}
    input[type="text"], input[type="number"] {{ padding: 6px 8px; border: 1px solid #ddd; border-radius: 6px; }}
  </style>
</head>
<body>
  <h1>Breathalyzer Leaderboard</h1>
  <div class="bar">
    <strong>Status:</strong> {ready_badge}
    <button id="readyBtn">Ready: Blow!</button>
    <span id="msg"></span>
  </div>

  <table>
    <thead><tr><th>#</th><th>Name</th><th>BAC</th><th>When</th></tr></thead>
    <tbody>
      {''.join(rows) or '<tr><td colspan="4">No readings yet</td></tr>'}
    </tbody>
  </table>

  <!-- Manual submit for testing -->
  <form id="manual">
    <label>Name <input type="text" name="name" placeholder="e.g., Jack" required></label>
    <label>BAC <input type="number" name="bac" min="0" max="0.5" step="0.001" required></label>
    <button type="submit">Add reading</button>
    <small>(For initial testing; your sensor will POST to /api/reading)</small>
  </form>

  <script>
    const readyBtn = document.getElementById('readyBtn');
    const msg = document.getElementById('msg');
    readyBtn.onclick = async () => {{
      msg.textContent = '...';
      try {{
        const r = await fetch('/api/ready', {{ method:'POST' }});
        const j = await r.json();
        msg.textContent = j.ok ? `Ready for ${j.ready_for_secs}s` : 'Error';
        setTimeout(() => location.reload(), 500); // refresh status badge
      }} catch (e) {{ msg.textContent = 'Network error'; }}
    }};
    document.getElementById('manual').onsubmit = async (e) => {{
      e.preventDefault();
      const fd = new FormData(e.target);
      const name = fd.get('name'); const bac = fd.get('bac');
      const body = new URLSearchParams({{name, bac}}).toString();
      const r = await fetch('/api/reading', {{
        method:'POST',
        headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
        body
      }});
      if (r.ok) location.reload(); else alert('Submit failed');
    }};
  </script>
</body>
</html>"""

# ---------------- Hardware hook ----------------
def set_breathalyzer_ready(seconds: int = 20):
    """
    This is the hook you replace later with real I/O.
    For now we just flag a window and print. Options later:
      - Toggle a Raspberry Pi GPIO pin high for 'seconds'
      - Send a local HTTP/UDP/TCP or Particle Cloud event to your Photon
      - Drive an LCD prompt 'Ready: Blow!'
    """
    global ready_until
    ready_until = time.time() + max(1, int(seconds))
    print(f"[READY] Breathalyzer ready for {seconds}s")

# ---------------- Main loop ----------------
def serve():
    load_store()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen(5)
        print(f"Serving on http://{HOST or '0.0.0.0'}:{PORT}")

        while True:
            conn, addr = s.accept()
            with conn:
                try:
                    method, path, headers, body = read_http_request(conn)
                    resp = route(method, path, headers, body)
                except ValueError as ve:
                    resp = http_response(400, {"Connection":"close", "Content-Type":"text/plain"},
                                         f"Bad Request: {ve}".encode("utf-8"))
                except Exception as e:
                    print("ERROR:", e)
                    resp = http_response(400, {"Connection":"close", "Content-Type":"text/plain"},
                                         b"Bad Request")
                conn.sendall(resp)

if __name__ == "__main__":
    serve()
