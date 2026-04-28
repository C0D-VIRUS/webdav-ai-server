"""
File Monitor — watches localFolder/ for changes and processes -/gw markers.

Uses the `watchdog` library for instant file-change detection.
Falls back to periodic polling if watchdog is not installed.

Key features:
  • Debouncing — ignores rapid successive saves (editors often save twice)
  • Self-write prevention — after writing an AI response back, the next change
    on that file is ignored so we don't enter an infinite loop
  • Concurrent processing — each detected change runs in its own thread
"""

import os
import time
import threading
from datetime import datetime

from src.config import (
    WATCH_FOLDER, SCAN_INTERVAL,
    DEBOUNCE_SECONDS, SELF_WRITE_COOLDOWN,
)
from src.utils import (
    get_file_hash, has_ai_marker, extract_prompt_after_marker,
    replace_marker_with_response, detect_code_request,
    generate_session_id, timestamp, is_temp_file,
)
from src.gemini_client import send_to_gemini


# ─── Shared state ────────────────────────────────────────────────────────────

_file_hashes = {}           # path → md5
_hashes_lock = threading.Lock()

_sessions = {}              # session_id → {file, status, …}
_sessions_lock = threading.Lock()

# Paths we recently wrote to (self-write prevention)
_skip_paths = {}            # path → expiry timestamp
_skip_lock = threading.Lock()

# Debounce: path → last-event timestamp
_last_event = {}
_debounce_lock = threading.Lock()


# ─── Public API ──────────────────────────────────────────────────────────────

def get_sessions():
    """Return a snapshot of all tracked sessions."""
    with _sessions_lock:
        return dict(_sessions)


# ─── Session management ─────────────────────────────────────────────────────

def _create_session(file_path, action="changed"):
    sid = generate_session_id("mon")
    with _sessions_lock:
        _sessions[sid] = {
            "file": file_path,
            "status": "processing",
            "action": action,
            "created_at": timestamp(),
        }
    return sid


def _update_session(sid, status, message=None):
    with _sessions_lock:
        if sid in _sessions:
            _sessions[sid]["status"] = status
            _sessions[sid]["updated_at"] = timestamp()
            if message:
                _sessions[sid]["message"] = message


# ─── Self-write prevention ──────────────────────────────────────────────────

def _mark_self_write(path):
    """Mark *path* so the next change is ignored (we just wrote to it)."""
    with _skip_lock:
        _skip_paths[path] = time.time() + SELF_WRITE_COOLDOWN


def _should_skip(path):
    """Return True if *path* was recently written by us."""
    with _skip_lock:
        expiry = _skip_paths.get(path)
        if expiry is None:
            return False
        if time.time() < expiry:
            return True
        # expired — remove
        del _skip_paths[path]
        return False


# ─── Debounce ────────────────────────────────────────────────────────────────

def _debounce_ok(path):
    """Return True if enough time has passed since the last event on *path*."""
    now = time.time()
    with _debounce_lock:
        last = _last_event.get(path, 0)
        if now - last < DEBOUNCE_SECONDS:
            return False
        _last_event[path] = now
        return True


# ─── Core processing ────────────────────────────────────────────────────────

def _process_file(file_path, sid):
    """Read file, send to Gemini if marker present, write response back."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as e:
        print(f"[{sid}] Cannot read {file_path}: {e}")
        _update_session(sid, "error", str(e))
        return

    if not has_ai_marker(content):
        print(f"[{sid}] No -/gw marker → normal save")
        _update_session(sid, "completed", "Normal save")
        return

    prompt = extract_prompt_after_marker(content)
    if not prompt:
        print(f"[{sid}] -/gw marker found but no prompt text after it")
        _update_session(sid, "completed", "Empty prompt — skipped")
        return

    is_code = detect_code_request(prompt)
    kind = "CODE" if is_code else "EXPLANATION"
    print(f"[{sid}] Detected request type: {kind}")
    _update_session(sid, "calling_ai", f"Sending {kind} request to Gemini")

    # Provide instant visual feedback in the file (NOT starting with -/gw to avoid re-triggering)
    thinking_text = f"// [AI working on: {prompt}]"
    thinking_content = replace_marker_with_response(content, thinking_text)
    try:
        _mark_self_write(file_path)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(thinking_content)
        with _hashes_lock:
            _file_hashes[file_path] = get_file_hash(file_path)
    except Exception:
        pass

    # Send original content to Gemini
    response = send_to_gemini(file_content=content, instruction=prompt, request_type=kind, file_path=file_path)

    # Re-read file to preserve any edits the user made while waiting
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            current_content = f.read()
    except Exception:
        current_content = thinking_content

    if not response:
        print(f"[{sid}] No response from Gemini")
        _update_session(sid, "failed", "No AI response")
        # Write error as a comment — NOT starting with -/gw to prevent re-triggering
        error_text = f"// [AI Error — quota/rate limit hit. Try again in ~1 min. Prompt: {prompt}]"
        new_content = current_content.replace(thinking_text, error_text)
    else:
        response = _strip_code_fences(response)
        new_content = current_content.replace(thinking_text, response)
        if thinking_text not in current_content:
            # Fallback: replace whatever -/gw line remains
            new_content = replace_marker_with_response(current_content, response)

    try:
        _mark_self_write(file_path)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        with _hashes_lock:
            _file_hashes[file_path] = get_file_hash(file_path)
        print(f"[{sid}] ✅ Updated {file_path}")
        _update_session(sid, "completed", "AI response written")
    except Exception as e:
        print(f"[{sid}] Error writing {file_path}: {e}")
        _update_session(sid, "error", str(e))


def _strip_code_fences(text):
    """Remove leading/trailing markdown code fences (```lang ... ```)."""
    stripped = text.strip()
    if stripped.startswith("```"):
        # Remove first line (```lang)
        lines = stripped.split("\n", 1)
        if len(lines) > 1:
            stripped = lines[1]
        else:
            stripped = ""
        # Remove trailing ```
        if stripped.rstrip().endswith("```"):
            stripped = stripped.rstrip()[:-3].rstrip()

    # Also strip any trailing -/gw marker the AI occasionally echoes back
    lines = stripped.rstrip().splitlines()
    while lines and lines[-1].strip().startswith("-/gw"):
        lines.pop()
    stripped = "\n".join(lines)

    return stripped


# ─── File-change handler (called by both watchdog and poller) ────────────────

def handle_file_change(file_path, action="changed"):
    """Handle a detected file change — debounce, skip self-writes, process."""
    filename = os.path.basename(file_path)
    if is_temp_file(filename):
        return

    if _should_skip(file_path):
        return

    if not _debounce_ok(file_path):
        return

    print(f"\n[FILE {action.upper()}] {file_path}")
    sid = _create_session(file_path, action)

    thread = threading.Thread(
        target=_process_file,
        args=(file_path, sid),
        daemon=True,
    )
    thread.start()


# ═══════════════════════════════════════════════════════════════════════════
#  Watchdog-based watcher (preferred)
# ═══════════════════════════════════════════════════════════════════════════

_watchdog_available = False

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    _watchdog_available = True
except ImportError:
    pass


class _ChangeHandler(FileSystemEventHandler if _watchdog_available else object):
    """Watchdog event handler — forwards file events to handle_file_change."""

    def on_modified(self, event):
        if not event.is_directory:
            handle_file_change(event.src_path, "changed")

    def on_created(self, event):
        if not event.is_directory:
            handle_file_change(event.src_path, "new")


def start_watchdog(watch_folder=None):
    """
    Start the watchdog observer. Returns the observer thread.
    Raises ImportError if watchdog is not installed.
    """
    if not _watchdog_available:
        raise ImportError("watchdog library not installed")

    folder = watch_folder or WATCH_FOLDER
    observer = Observer()
    observer.schedule(_ChangeHandler(), folder, recursive=True)
    observer.daemon = True
    observer.start()
    print(f"[MONITOR] Watchdog watching: {folder}")
    return observer


# ═══════════════════════════════════════════════════════════════════════════
#  Polling-based watcher (fallback)
# ═══════════════════════════════════════════════════════════════════════════

def _poll_once(watch_folder):
    """One pass of the polling scanner."""
    current_files = set()

    for root, _dirs, files in os.walk(watch_folder):
        for filename in files:
            if is_temp_file(filename):
                continue

            path = os.path.join(root, filename)
            current_files.add(path)
            current_hash = get_file_hash(path)

            with _hashes_lock:
                prev_hash = _file_hashes.get(path)
                if prev_hash is None:
                    _file_hashes[path] = current_hash
                    handle_file_change(path, "new")
                elif prev_hash != current_hash:
                    _file_hashes[path] = current_hash
                    handle_file_change(path, "changed")

    # Detect deletions
    with _hashes_lock:
        deleted = set(_file_hashes.keys()) - current_files
        for path in deleted:
            del _file_hashes[path]
            print(f"\n[FILE DELETED] {path}")


def start_polling(watch_folder=None, interval=None):
    """
    Start polling in the current thread (blocking).
    Call this in a daemon thread.
    """
    folder = watch_folder or WATCH_FOLDER
    pause = interval or SCAN_INTERVAL
    print(f"[MONITOR] Polling {folder} every {pause}s")

    while True:
        try:
            _poll_once(folder)
        except Exception as e:
            print(f"[MONITOR ERROR] {e}")
        time.sleep(pause)


# ═══════════════════════════════════════════════════════════════════════════
#  Unified start function
# ═══════════════════════════════════════════════════════════════════════════

def _populate_hashes_only(watch_folder):
    """Silently populate the hash table from existing files WITHOUT triggering any AI.
    Called once at startup so we only detect FUTURE changes, not old files."""
    count = 0
    for root, _dirs, files in os.walk(watch_folder):
        for filename in files:
            if is_temp_file(filename):
                continue
            path = os.path.join(root, filename)
            with _hashes_lock:
                _file_hashes[path] = get_file_hash(path)
            count += 1
    return count


def start_monitor(watch_folder=None):
    """
    Start the file monitor — uses watchdog if available, else falls back
    to polling.  Returns immediately (starts background threads).
    """
    folder = watch_folder or WATCH_FOLDER

    # Initial scan: ONLY populate hashes, do NOT trigger AI on pre-existing files
    print("[MONITOR] Initial scan …")
    n = _populate_hashes_only(folder)
    print(f"[MONITOR] Initial scan done ({n} files indexed, watching for new changes)")

    if _watchdog_available:
        try:
            start_watchdog(folder)
            return
        except Exception as e:
            print(f"[MONITOR] Watchdog failed ({e}), falling back to polling")

    # Fallback: polling in a background thread
    t = threading.Thread(target=start_polling, args=(folder,), daemon=True)
    t.start()
