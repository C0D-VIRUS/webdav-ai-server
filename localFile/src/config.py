"""
Configuration settings for the combined WebDAV + File Monitor server.
All paths are relative to the project root.
"""

import os

# ============== PATHS ==============
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WATCH_FOLDER = os.path.join(BASE_DIR, "localFolder")

# ============== GEMINI API ==============
# Can be overridden via environment variable GEMINI_API_KEY
GEMINI_API_KEY = os.environ.get(
    "GEMINI_API_KEY",
    "AIzaSyA_WEuTLr0nQe6cRxxEzGReLB1RPAqVvXU"
)
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "models/gemini-2.5-flash")
GEMINI_API_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
)

# ============== SERVER SETTINGS ==============
WEBDAV_PORT = int(os.environ.get("WEBDAV_PORT", "8000"))
HOST = "0.0.0.0"

# ============== MONITOR SETTINGS ==============
SCAN_INTERVAL = 1          # seconds between polling checks (fallback mode)
DEBOUNCE_SECONDS = 0.2     # ignore rapid re-saves within this window
SELF_WRITE_COOLDOWN = 1.0  # seconds to ignore a file after we write to it

# ============== SESSION SETTINGS ==============
SESSION_TIMEOUT = 1800     # 30 minutes of inactivity before cleanup
MAX_RETRIES = 5            # Gemini API retry count
RETRY_DELAY = 10           # base delay between retries (seconds)

# ============== DEFAULT FILES ==============
# Files created in every new WebDAV session folder
DEFAULT_FILES = {
    "example.py": (
        "# Write your Python code here\n"
        "# To use AI: on a new line type the dash-slash-gw marker\n"
        "#   followed by your prompt, then save the file.\n"
        "# The AI will replace the marker line with its response.\n"
        "\n"
        "def main():\n"
        "    pass\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
    ),
    "example.cpp": (
        "// Write your C++ code here\n"
        "// To use AI: on a new line type the dash-slash-gw marker\n"
        "//   followed by your prompt, then save the file.\n"
        "// The AI will replace the marker line with its response.\n"
        "\n"
        "#include <iostream>\n"
        "\n"
        "int main() {\n"
        "    return 0;\n"
        "}\n"
    ),
}

# ============== MARKER ==============
AI_MARKER = "-/gw"