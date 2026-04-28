"""
Utility functions: hashing, IP detection, marker helpers, session IDs.
"""

import os
import hashlib
import re
import socket
import subprocess
import uuid
from datetime import datetime

from src.config import AI_MARKER


# ─── Network ────────────────────────────────────────────────────────────────

def get_ip_address():
    """Get this machine's LAN IP address."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # Doesn't have to be reachable, just forces socket resolution
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"



# ─── File hashing ────────────────────────────────────────────────────────────

def get_file_hash(file_path):
    """Calculate MD5 hash of file content."""
    try:
        with open(file_path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    except Exception as e:
        print(f"[ERROR] Hashing {file_path}: {e}")
        return None


# ─── AI marker helpers ──────────────────────────────────────────────────────

def has_ai_marker(content):
    """Check whether *content* contains the AI marker (-/gw)."""
    return AI_MARKER in content


def extract_prompt_after_marker(content):
    """Return the text that follows the first -/gw marker, or None."""
    pattern = re.escape(AI_MARKER) + r"\s*"
    match = re.search(pattern, content)
    if match:
        prompt = content[match.end():].strip()
        return prompt if prompt else None
    return None


def replace_marker_with_response(content, response):
    """Replace the -/gw marker and everything after it with *response*."""
    pattern = re.escape(AI_MARKER) + r".*"
    return re.sub(pattern, response, content, count=1, flags=re.DOTALL)


def detect_code_request(text):
    """Heuristic: does the prompt look like a code request?"""
    keywords = [
        "code", "function", "class", "script", "program",
        "write", "implement", "create", "build", "develop",
        "algorithm", "def ", "int main", "import", "include",
    ]
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)


# ─── IDs & timestamps ───────────────────────────────────────────────────────

def generate_session_id(prefix="sess"):
    """Generate a short unique session ID."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def timestamp():
    """ISO-8601 timestamp for the current moment."""
    return datetime.now().isoformat()


# ─── Filesystem ──────────────────────────────────────────────────────────────

def ensure_dir(path):
    """Create *path* and all parents if they don't exist."""
    os.makedirs(path, exist_ok=True)


def is_temp_file(filename):
    """Return True for temporary / hidden files that should be ignored."""
    if filename.startswith("."):
        return True
    if filename.startswith("~"):
        return True
    if filename.endswith(".swp") or filename.endswith(".tmp"):
        return True
    if filename.startswith(".__"):
        return True
    # macOS resource forks
    if filename == ".DS_Store":
        return True
    return False