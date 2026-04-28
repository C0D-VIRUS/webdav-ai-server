"""
WebDAV Handler — serves files from localFolder/ with per-connection sessions.

When a WebDAV client (macOS Finder, Windows Explorer, etc.) connects to
dav://<ip>:8000/ a unique session folder is created under localFolder/.
Each session gets a default file (file.cpp).  Sessions are cleaned up
after 30 minutes of inactivity or when the server shuts down.

Implements the WebDAV methods required by common clients:
  OPTIONS, HEAD, GET, PUT, DELETE, MKCOL, PROPFIND, PROPPATCH,
  MOVE, COPY, LOCK, UNLOCK
"""

import os
import shutil
import time
import threading
import xml.etree.ElementTree as ET
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, unquote, quote
from email.utils import formatdate

from src.config import WATCH_FOLDER, DEFAULT_FILES, SESSION_TIMEOUT, WEBDAV_PORT
from src.utils import get_ip_address, ensure_dir, generate_session_id


# ─── Session registry ───────────────────────────────────────────────────────

_sessions = {}          # session_id → {"path": str, "last_access": float}
_sessions_lock = threading.Lock()


def _touch_session(session_id):
    """Update the last-access timestamp so the session stays alive."""
    with _sessions_lock:
        if session_id in _sessions:
            _sessions[session_id]["last_access"] = time.time()


def get_or_create_session(ip):
    """Get existing session for IP, or create a new one. Returns (id, path)."""
    with _sessions_lock:
        for sid, info in _sessions.items():
            if info.get("ip") == ip:
                info["last_access"] = time.time()
                return sid, info["path"]

    sid = generate_session_id("dav")
    path = os.path.join(WATCH_FOLDER, sid)
    ensure_dir(path)

    for filename, content in DEFAULT_FILES.items():
        with open(os.path.join(path, filename), "w", encoding="utf-8") as f:
            f.write(content)

    with _sessions_lock:
        _sessions[sid] = {"path": path, "last_access": time.time(), "ip": ip}

    print(f"[SESSION] Created {sid} for {ip}")
    return sid, path


def delete_session(session_id):
    """Remove a session folder from disk and registry."""
    with _sessions_lock:
        info = _sessions.pop(session_id, None)
    if info and os.path.exists(info["path"]):
        try:
            shutil.rmtree(info["path"])
            print(f"[SESSION] Deleted {session_id}")
        except Exception as e:
            print(f"[SESSION] Error deleting {session_id}: {e}")


def resolve_session(path, ip=None):
    """
    Given a URL path like /dav_abcd1234/subdir/file.cpp
    return (session_id, session_root, relative_path) or (None, None, None).
    """
    parts = path.strip("/").split("/", 1)
    if not parts or not parts[0]:
        return None, None, None

    candidate = parts[0]
    if candidate in (".", "..") or candidate.startswith("."):
        return None, None, None

    session_root = os.path.join(WATCH_FOLDER, candidate)
    rel = parts[1] if len(parts) > 1 else ""

    with _sessions_lock:
        if candidate in _sessions:
            _sessions[candidate]["last_access"] = time.time()
            if ip and not _sessions[candidate].get("ip"):
                _sessions[candidate]["ip"] = ip
        else:
            _sessions[candidate] = {"path": session_root, "last_access": time.time(), "ip": ip}

    return candidate, session_root, rel


def list_sessions():
    """Return a dict copy of all sessions."""
    with _sessions_lock:
        return dict(_sessions)


# ─── Cleanup thread ─────────────────────────────────────────────────────────

def cleanup_loop(timeout=None):
    """Run forever, deleting sessions that exceed *timeout* seconds idle.
    Also clears old/orphaned dav_* folders instantly on startup and periodically.
    """
    timeout = timeout or SESSION_TIMEOUT
    # Wait for the initial file monitor scan to complete before first cleanup
    time.sleep(5)
    while True:
        now = time.time()
        with _sessions_lock:
            expired = [
                sid for sid, info in _sessions.items()
                if now - info["last_access"] > timeout
            ]
            active_sids = set(_sessions.keys())

        for sid in expired:
            delete_session(sid)

        # Cleanup orphaned/old folders left on disk
        if os.path.exists(WATCH_FOLDER):
            for item in os.listdir(WATCH_FOLDER):
                if item not in active_sids:
                    # ONLY delete if it's an auto-generated sandboxed dav_ session
                    if item.startswith("dav_"):
                        p = os.path.join(WATCH_FOLDER, item)
                        if os.path.isdir(p):
                            try:
                                shutil.rmtree(p)
                                print(f"[CLEANUP] Removed old auto-session: {item}")
                            except Exception:
                                pass

        time.sleep(60)


# ─── MIME helper ─────────────────────────────────────────────────────────────

_MIME = {
    ".cpp": "text/x-c++src", ".c": "text/x-csrc", ".h": "text/x-chdr",
    ".py": "text/x-python", ".js": "application/javascript",
    ".ts": "application/typescript",
    ".html": "text/html", ".htm": "text/html",
    ".css": "text/css", ".json": "application/json",
    ".xml": "application/xml", ".txt": "text/plain",
    ".md": "text/markdown", ".sh": "text/x-shellscript",
    ".java": "text/x-java", ".rs": "text/x-rust",
    ".go": "text/x-go", ".rb": "text/x-ruby",
    ".swift": "text/x-swift",
}


def _mime_for(path):
    ext = os.path.splitext(path)[1].lower()
    return _MIME.get(ext, "application/octet-stream")


# ─── XML helpers for PROPFIND responses ──────────────────────────────────────

_DAV_NS = "DAV:"


def _propfind_entry(href, is_collection, size=0, mtime=None):
    """Build one <d:response> XML element."""
    mtime_str = formatdate(mtime, usegmt=True) if mtime else formatdate(usegmt=True)
    resource_type = "<d:collection/>" if is_collection else ""
    return f"""<d:response>
<d:href>{quote(href)}</d:href>
<d:propstat>
<d:prop>
<d:displayname>{os.path.basename(href)}</d:displayname>
<d:resourcetype>{resource_type}</d:resourcetype>
<d:getcontentlength>{size}</d:getcontentlength>
<d:getlastmodified>{mtime_str}</d:getlastmodified>
</d:prop>
<d:status>HTTP/1.1 200 OK</d:status>
</d:propstat>
</d:response>
"""


def _propfind_xml(entries):
    """Wrap a list of response entries into a multistatus document."""
    body = '<?xml version="1.0" encoding="utf-8"?>\n'
    body += '<d:multistatus xmlns:d="DAV:">\n'
    body += "".join(entries)
    body += "</d:multistatus>\n"
    return body.encode("utf-8")


# ═══════════════════════════════════════════════════════════════════════════
#  WebDAV request handler
# ═══════════════════════════════════════════════════════════════════════════

class WebDAVHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "LocalFileDAV/2.0"

    def handle(self):
        try:
            super().handle()
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
            pass

    # Suppress default stderr logging
    def log_message(self, fmt, *args):
        print(f"[{self.client_address[0]}] {fmt % args}")

    # ── helpers ──────────────────────────────────────────────────────────

    def _send(self, code, body=b"", content_type="text/plain; charset=utf-8", extra_headers=None):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", len(body))
        # Cloudflare Tunnel compatibility headers
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods",
            "OPTIONS, GET, HEAD, PUT, DELETE, MKCOL, PROPFIND, PROPPATCH, MOVE, COPY, LOCK, UNLOCK")
        self.send_header("Access-Control-Allow-Headers",
            "Authorization, Content-Type, Depth, Destination, If, Lock-Token, Overwrite, Timeout, X-Requested-With")
        self.send_header("Access-Control-Expose-Headers", "DAV, content-length, Allow")
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _resolve(self):
        """Resolve the request path to (session_id, abs_path) or redirect / create session."""
        raw = unquote(urlparse(self.path).path)
        return raw, *resolve_session(raw, self.client_address[0])

    def _abs_path(self, session_root, rel):
        """Join and normalise, preventing directory traversal."""
        joined = os.path.normpath(os.path.join(session_root, rel))
        if not joined.startswith(session_root):
            return None
        return joined

    # ── OPTIONS ──────────────────────────────────────────────────────────

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Allow", "OPTIONS, GET, HEAD, PUT, DELETE, MKCOL, PROPFIND, PROPPATCH, MOVE, COPY, LOCK, UNLOCK")
        self.send_header("DAV", "1, 2")
        self.send_header("MS-Author-Via", "DAV")
        # Cloudflare Tunnel / browser preflight compatibility
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods",
            "OPTIONS, GET, HEAD, PUT, DELETE, MKCOL, PROPFIND, PROPPATCH, MOVE, COPY, LOCK, UNLOCK")
        self.send_header("Access-Control-Allow-Headers",
            "Authorization, Content-Type, Depth, Destination, If, Lock-Token, Overwrite, Timeout, X-Requested-With")
        self.send_header("Access-Control-Max-Age", "3600")
        self.send_header("Content-Length", "0")
        self.end_headers()

    # ── HEAD ─────────────────────────────────────────────────────────────

    def do_HEAD(self):
        self._handle_get(head_only=True)

    # ── GET ──────────────────────────────────────────────────────────────

    def do_GET(self):
        self._handle_get()

    def _handle_get(self, head_only=False):
        raw, sid, session_root, rel = self._resolve()

        # Root page — create session & redirect
        if raw == "/" or raw == "":
            sid, path = get_or_create_session(self.client_address[0])
            self.send_response(302)
            self.send_header("Location", f"/{sid}/")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        if sid is None:
            self._send(400, b"Invalid path")
            return

        abs_path = self._abs_path(session_root, rel)
        if abs_path is None:
            self._send(403, b"Forbidden")
            return

        if not os.path.exists(abs_path):
            if not rel:
                ensure_dir(abs_path)
                for filename, content in DEFAULT_FILES.items():
                    with open(os.path.join(abs_path, filename), "w", encoding="utf-8") as f:
                        f.write(content)
                print(f"[FOLDER] Auto-created named workspace: {sid}")
            else:
                self._send(404, b"File not found")
                return

        if os.path.isdir(abs_path):
            body = self._dir_listing_html(sid, abs_path, rel).encode("utf-8")
            if head_only:
                self._send(200, b"", "text/html; charset=utf-8")
            else:
                self._send(200, body, "text/html; charset=utf-8")

        elif os.path.isfile(abs_path):
            with open(abs_path, "rb") as f:
                data = f.read()
            ct = _mime_for(abs_path) + "; charset=utf-8"
            if head_only:
                self._send(200, b"", ct)
            else:
                self._send(200, data, ct)
        else:
            self._send(404, b"File not found")

    def _dir_listing_html(self, sid, dir_path, rel):
        ip = get_ip_address()
        trail = f"/{rel}" if rel else ""
        html = f"""<!DOCTYPE html>
<html><head><title>Session: {sid}</title>
<style>
body {{ font-family: system-ui, -apple-system, sans-serif; margin: 40px; color: #1a1a1a; }}
h1 {{ color: #333; }}
.file {{ padding: 8px 12px; margin: 4px 0; background: #f7f7f7; border-radius: 6px; }}
.file:hover {{ background: #eef; }}
a {{ color: #0066cc; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
.info {{ background: #f0f4ff; padding: 14px 18px; border-radius: 8px; margin-bottom: 20px; font-size: 14px; }}
code {{ background: #e8e8e8; padding: 2px 6px; border-radius: 3px; font-size: 13px; }}
</style>
</head><body>
<h1>📂 {sid}{trail}</h1>
<div class="info">
  WebDAV: <code>dav://{ip}:{WEBDAV_PORT}/{sid}/</code><br>
  Use <code>-/gw your prompt</code> inside any file to trigger AI completion.
</div>
<p><a href="/">← Home</a></p>
<h2>Files</h2>
"""
        for name in sorted(os.listdir(dir_path)):
            href = f"/{sid}/{rel + '/' if rel else ''}{name}"
            icon = "📁" if os.path.isdir(os.path.join(dir_path, name)) else "📄"
            html += f'<div class="file">{icon} <a href="{href}">{name}</a></div>\n'
        html += "</body></html>"
        return html

    # ── PUT ──────────────────────────────────────────────────────────────

    def do_PUT(self):
        raw, sid, session_root, rel = self._resolve()
        if sid is None:
            self._send(400, b"Invalid path")
            return
        if not rel:
            self._send(400, b"Filename required")
            return

        abs_path = self._abs_path(session_root, rel)
        if abs_path is None:
            self._send(403, b"Forbidden")
            return

        ensure_dir(os.path.dirname(abs_path))

        length = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(length)

        with open(abs_path, "wb") as f:
            f.write(data)

        self._send(201, b"Created")

    # ── DELETE ───────────────────────────────────────────────────────────

    def do_DELETE(self):
        raw, sid, session_root, rel = self._resolve()
        if sid is None:
            self._send(400, b"Invalid path")
            return

        abs_path = self._abs_path(session_root, rel)
        if abs_path is None:
            self._send(403, b"Forbidden")
            return

        if os.path.isfile(abs_path):
            os.remove(abs_path)
            self._send(204)
        elif os.path.isdir(abs_path):
            shutil.rmtree(abs_path)
            self._send(204)
        else:
            self._send(404, b"Not found")

    # ── MKCOL (create directory) ─────────────────────────────────────────

    def do_MKCOL(self):
        raw, sid, session_root, rel = self._resolve()
        if sid is None:
            self._send(400, b"Invalid path")
            return

        abs_path = self._abs_path(session_root, rel)
        if abs_path is None:
            self._send(403, b"Forbidden")
            return

        if os.path.exists(abs_path):
            self._send(405, b"Already exists")
            return

        ensure_dir(abs_path)
        self._send(201, b"Created")

    # ── PROPFIND ─────────────────────────────────────────────────────────

    def do_PROPFIND(self):
        raw = unquote(urlparse(self.path).path)
        depth = self.headers.get("Depth", "1")

        # Read and discard request body (some clients send XML body)
        length = int(self.headers.get("Content-Length", 0))
        if length:
            self.rfile.read(length)

        # Root PROPFIND — auto-create a session
        if raw == "/" or raw == "":
            sid, path = get_or_create_session(self.client_address[0])
            entries = []
            # Entry for the root itself redirecting to the session
            entries.append(_propfind_entry("/", True))
            entries.append(_propfind_entry(f"/{sid}/", True))

            body = _propfind_xml(entries)
            self._send(207, body, "application/xml; charset=utf-8")
            return

        sid, session_root, rel = resolve_session(raw, self.client_address[0])
        if sid is None:
            self._send(400, b"Invalid path")
            return

        abs_path = self._abs_path(session_root, rel)
        if abs_path is None:
            self._send(403, b"Forbidden")
            return

        if not os.path.exists(abs_path):
            if not rel:
                ensure_dir(abs_path)
                for filename, content in DEFAULT_FILES.items():
                    with open(os.path.join(abs_path, filename), "w", encoding="utf-8") as f:
                        f.write(content)
                print(f"[FOLDER] Auto-created named workspace: {sid}")
            else:
                self._send(404, b"Not found")
                return

        entries = []
        if os.path.isdir(abs_path):
            entries.append(_propfind_entry(raw.rstrip("/") + "/", True, mtime=os.path.getmtime(abs_path)))
            if depth != "0":
                for name in os.listdir(abs_path):
                    fpath = os.path.join(abs_path, name)
                    is_dir = os.path.isdir(fpath)
                    sz = 0 if is_dir else os.path.getsize(fpath)
                    href = raw.rstrip("/") + "/" + name + ("/" if is_dir else "")
                    entries.append(_propfind_entry(href, is_dir, sz, os.path.getmtime(fpath)))
        else:
            sz = os.path.getsize(abs_path)
            entries.append(_propfind_entry(raw, False, sz, os.path.getmtime(abs_path)))

        body = _propfind_xml(entries)
        self._send(207, body, "application/xml; charset=utf-8")

    # ── PROPPATCH (stub — always succeed) ────────────────────────────────

    def do_PROPPATCH(self):
        length = int(self.headers.get("Content-Length", 0))
        if length:
            self.rfile.read(length)
        self._send(207, _propfind_xml([]), "application/xml; charset=utf-8")

    # ── MOVE ─────────────────────────────────────────────────────────────

    def do_MOVE(self):
        raw, sid, session_root, rel = self._resolve()
        if sid is None:
            self._send(400, b"Invalid path")
            return

        src = self._abs_path(session_root, rel)
        dest_header = self.headers.get("Destination", "")
        if not dest_header:
            self._send(400, b"Destination header required")
            return

        dest_path = unquote(urlparse(dest_header).path)
        _, d_sid, d_root, d_rel = dest_path, *resolve_session(dest_path)
        if d_sid is None:
            self._send(400, b"Invalid destination path")
            return

        dst = self._abs_path(d_root, d_rel)
        if src is None or dst is None:
            self._send(403, b"Forbidden")
            return

        if not os.path.exists(src):
            self._send(404, b"Source not found")
            return

        ensure_dir(os.path.dirname(dst))
        overwrite = self.headers.get("Overwrite", "T") == "T"
        code = 204 if os.path.exists(dst) else 201
        if os.path.exists(dst) and not overwrite:
            self._send(412, b"Destination exists")
            return

        shutil.move(src, dst)
        self._send(code)

    # ── COPY ─────────────────────────────────────────────────────────────

    def do_COPY(self):
        raw, sid, session_root, rel = self._resolve()
        if sid is None:
            self._send(400, b"Invalid path")
            return

        src = self._abs_path(session_root, rel)
        dest_header = self.headers.get("Destination", "")
        if not dest_header:
            self._send(400, b"Destination header required")
            return

        dest_path = unquote(urlparse(dest_header).path)
        _, d_sid, d_root, d_rel = dest_path, *resolve_session(dest_path)
        if d_sid is None:
            self._send(400, b"Invalid destination path")
            return

        dst = self._abs_path(d_root, d_rel)
        if src is None or dst is None:
            self._send(403, b"Forbidden")
            return

        if not os.path.exists(src):
            self._send(404, b"Source not found")
            return

        ensure_dir(os.path.dirname(dst))
        code = 204 if os.path.exists(dst) else 201

        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
        self._send(code)

    # ── LOCK / UNLOCK (stubs for client compatibility) ───────────────────

    def do_LOCK(self):
        length = int(self.headers.get("Content-Length", 0))
        if length:
            self.rfile.read(length)

        token = f"opaquelocktoken:{generate_session_id('lock')}"
        xml = f"""<?xml version="1.0" encoding="utf-8"?>
<d:prop xmlns:d="DAV:">
<d:lockdiscovery>
<d:activelock>
<d:locktype><d:write/></d:locktype>
<d:lockscope><d:exclusive/></d:lockscope>
<d:locktoken><d:href>{token}</d:href></d:locktoken>
<d:timeout>Second-3600</d:timeout>
</d:activelock>
</d:lockdiscovery>
</d:prop>"""
        self._send(200, xml.encode("utf-8"), "application/xml; charset=utf-8",
                   {"Lock-Token": f"<{token}>"})

    def do_UNLOCK(self):
        self._send(204)


# ═══════════════════════════════════════════════════════════════════════════
#  Server factory
# ═══════════════════════════════════════════════════════════════════════════

class ThreadedDAVServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def run_server(host=None, port=None):
    """Start the WebDAV server (blocking)."""
    from src.config import HOST as _H, WEBDAV_PORT as _P
    host = host or _H
    port = port or _P
    server = ThreadedDAVServer((host, port), WebDAVHandler)
    print(f"[WEBDAV] Listening on {host}:{port}")
    server.serve_forever()
