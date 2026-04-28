#!/usr/bin/env python3
"""
Combined WebDAV File Server + AI-Powered File Monitor
=====================================================
Single entry point — starts:
  1. WebDAV server (serves files, auto-creates per-connection session folders)
  2. File monitor (watches localFolder/ for -/gw markers → Gemini AI)
  3. Session cleanup (removes stale session folders after 30 min)

Usage:
    python3 server.py
"""

import os
import sys
import threading

# Ensure project root is in sys.path so `from src.…` works
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import WATCH_FOLDER, WEBDAV_PORT, HOST, SESSION_TIMEOUT
from src.utils import get_ip_address, ensure_dir
from src.file_monitor import start_monitor
from src.webdav_handler import run_server, cleanup_loop


def main():
    ip = get_ip_address()

    print()
    print("=" * 62)
    print("  📁  WebDAV File Server  +  🤖 AI File Monitor")
    print("=" * 62)
    print(f"  Watch Folder : {WATCH_FOLDER}")
    print(f"  Server       : {ip}:{WEBDAV_PORT}")
    print()
    print("  Access URLs:")
    print(f"    WebDAV → dav://{ip}:{WEBDAV_PORT}/")
    print(f"    HTTP   → http://{ip}:{WEBDAV_PORT}/")
    print()
    print("  How it works:")
    print("    • Connect via WebDAV — a session folder is created for you")
    print("    • Edit any file and add  -/gw <prompt>  then save")
    print("    • The AI replaces your prompt with its response in-place")
    print("=" * 62)
    print()

    # Ensure the watch folder exists
    ensure_dir(WATCH_FOLDER)

    # 1) Session cleanup thread (removes idle sessions after 30 min)
    cleanup_thread = threading.Thread(
        target=cleanup_loop,
        args=(SESSION_TIMEOUT,),
        daemon=True,
    )
    cleanup_thread.start()

    # 2) File monitor (watchdog or polling — runs in background threads)
    start_monitor(WATCH_FOLDER)

    # 3) WebDAV server (runs in main thread — blocks)
    print(f"[READY] Server running. Press Ctrl+C to stop.\n")
    try:
        run_server(HOST, WEBDAV_PORT)
    except KeyboardInterrupt:
        print("\n\n[STOP] Shutting down …")
        print("Done.")


if __name__ == "__main__":
    main()