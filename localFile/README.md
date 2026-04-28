# WebDAV File Server + AI-Powered File Monitor

A combined Python server that provides WebDAV file access with automatic Gemini AI integration. Edit a file, add `-/gw` followed by a prompt, save — and the AI response replaces your prompt in-place.

## Features

- **WebDAV Server** — mount as a network drive from any device on the LAN
- **Per-connection sessions** — each WebDAV client gets its own isolated folder
- **AI-powered editing** — type `-/gw <prompt>` in any file, save, and the AI responds in-place
- **Multi-user concurrent** — multiple users can edit simultaneously without interference
- **Named folder access** — access `dav://ip:8000/myfolder` to open or auto-create a named folder
- **Auto-cleanup** — session folders are removed after 30 minutes of inactivity

## Project Structure

```
localFile/
├── server.py              ← Single entry point (start here)
├── src/
│   ├── __init__.py
│   ├── config.py          ← All settings (paths, API key, ports)
│   ├── utils.py           ← Hashing, IP detection, marker helpers
│   ├── gemini_client.py   ← Gemini API client with retry logic
│   ├── file_monitor.py    ← File watcher (watchdog + polling fallback)
│   └── webdav_handler.py  ← Full WebDAV server with session management
├── localFolder/           ← Watched folder (auto-created)
├── run_server.sh          ← Shell launcher
└── README.md
```

## Quick Start

### Windows

Double-click `run_server.bat` or run it from the command line:
```cmd
.\run_server.bat
```
*(This will automatically create a virtual environment and install dependencies)*

### macOS / Linux

```bash
# Option 1: Direct
python3 server.py

# Option 2: Shell script (auto-installs watchdog)
chmod +x run_server.sh
./run_server.sh
```

The server starts on port **8000** by default. You'll see:

```
  📁  WebDAV File Server  +  🤖 AI File Monitor
  Server       : 10.90.1.164:8000

  Access URLs:
    WebDAV → dav://10.90.1.164:8000/
    HTTP   → http://10.90.1.164:8000/
```

## How to Use

### 1. Connect via WebDAV

| Platform | How |
|----------|-----|
| **macOS Finder** | Go → Connect to Server → `dav://IP:8000/` |
| **Windows** | Map Network Drive → `http://IP:8000/` |
| **Linux** | `davfs2` or any WebDAV client |

Each connection creates a **session folder** with a default `file.cpp`.

### 2. AI-Powered Editing

Open any file in the session folder and add the `-/gw` marker:

```cpp
// My C++ file
#include <iostream>

int main() {
    return 0;
}
-/gw write a function to calculate fibonacci numbers
```

Save the file. The monitor detects the change, sends the prompt to Gemini AI, and replaces `-/gw …` with the AI's response:

```cpp
// My C++ file
#include <iostream>

int main() {
    return 0;
}
int fibonacci(int n) {
    if (n <= 1) return n;
    return fibonacci(n - 1) + fibonacci(n - 2);
}
```

### 3. Normal Editing

If you save a file **without** `-/gw`, it's saved normally — no AI call.

### 4. Named Folders

Access `dav://IP:8000/myfolder` to open or auto-create a named folder. Useful for persistent workspaces.

## Configuration

Edit `src/config.py` or set environment variables:

| Setting | Default | Env Variable |
|---------|---------|--------------|
| API Key | (built-in) | `GEMINI_API_KEY` |
| Model | `gemini-2.0-flash` | `GEMINI_MODEL` |
| Port | `8000` | `WEBDAV_PORT` |
| Session timeout | 30 min | — |
| Scan interval | 2 sec | — |

## How It Works (Technical)

1. **WebDAV Server** (`src/webdav_handler.py`): A threaded HTTP server implementing WebDAV methods (OPTIONS, PROPFIND, GET, PUT, DELETE, MKCOL, MOVE, COPY, LOCK, UNLOCK). Each new connection auto-creates a session folder.

2. **File Monitor** (`src/file_monitor.py`): Uses `watchdog` (or polling fallback) to detect file changes. On each change:
   - Debounces rapid saves (1-second window)
   - Checks if the file contains `-/gw`
   - If yes: extracts the prompt, sends to Gemini, writes response back
   - Prevents infinite loops via self-write detection

3. **Gemini Client** (`src/gemini_client.py`): Sends prompts to Google's Gemini API with automatic retry on rate-limit (429) errors.

## Stop the Server

Press `Ctrl+C` to stop gracefully.