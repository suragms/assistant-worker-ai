# ⚙️ ASSISTANT WORKER
### Modern AI Assistant personalized for Surag — Rebranded from MARK LV (55)

A real-time voice AI that can hear, see, speak, and control your computer — on any OS. Supports Windows, macOS, and Linux. Built on the Gemini Live API for native audio streaming, delivering zero subscriptions and total digital autonomy.

---

## ✨ Overview

Assistant Worker (rebranded from Jarvis/Mark-LV) features a redesigned modern, conversation-focused Windows 11 style UI. It features a modern 3-part layout (Header, Center Conversation Panel, and Bottom Input Bar), local wake-word detection using openwakeword, and zero cost/latency voice streaming.

---

## 🚀 Capabilities

### Core Features
| Feature | Description |
|---|---|
| 🧑‍🎤 Holographic Avatar | An animated human head in the HUD — real facial geometry, lit and drawn in software, no GPU or extra packages |
| 👄 Real Lip-Sync | ~50 mouth shapes a second from the audio's formants **and** the transcript — closures, spreads and rounds, not a volume meter |
| 🌍 Language-Free Mouth | Articulation is derived by Unicode reduction, so Latin, Cyrillic and Greek scripts all work from one rule set — and scripts that hide pronunciation fall back cleanly |
| 🙂 Facial Acting | Brows track the phrase, gaze saccades between fixations, natural blinking, a small nod on stressed syllables |
| 😐 Face as Status | Looks away while thinking, meets your eyes while listening, lids fall while asleep, glances down at new content |
| 🎚️ Push-to-Talk | Hold **Ctrl+Space** and the mic opens — closed the rest of the time. Truly global on Windows, window-scoped elsewhere |
| 🔇 Self-Echo Guard | Never answers its own last sentence: the tail of its own voice is recognised and dropped without muting you |
| 🪪 Runtime Self-Knowledge | Name, OS, abilities **and limits** are generated from the live system each session — rename it or add a plugin and it knows |
| 🎙️ Wake Word | Local **"Hey Assistant"** detection — sleeps until called, auto-sleeps after 2 min of silence, and never streams audio while asleep |
| ⚡ Instant Acknowledgment | Speaks a short, context-aware reply in **your language** the instant a longer task starts — no more silent waiting |
| 🚀 Faster Live Engine | Runs on the latest Gemini Models — roughly 2× faster time-to-first-word than the previous model |
| 🧩 Self-Describing Skills | Every bundled skill declares its own `TOOL` dict + handler and is auto-discovered at launch — adding one is a single file |
| 🧠 Recallable Memory | No size limit and nothing silently forgotten — the prompt carries what fits, the rest is looked up on demand from a local search |
| 👁️ Memory Panel | See every fact Assistant Worker has stored about you, when it learned it, and delete any of it in one click |
| ↩️ Undo | Take back what the assistant did — files it moved, renamed, created or wrote, and settings it changed |
| ⚠️ Real Confirmation | Shutdown, restart and WiFi wait for a button **you** press — the model cannot confirm its own irreversible actions |
| 🎧 Audio Device Picker | Choose the microphone and speakers by name, filtered to the short list your OS shows — and measured, so every entry actually works |
| 🔗 Session Continuity | A dropped connection, a voice change or a device change no longer wipes the conversation |
| 🧩 Plugin System | Drop a single `.py` file into `plugins/` — Assistant Worker learns a new skill on next launch |
| 📺 Video on the HUD | Plays YouTube, a local file or any video URL **where the avatar sits** — starts muted, sound on request |
| 🪜 Model Ladder | Gemini models in one measured order — a quota, a timeout or an outage steps to the next rung instead of failing |
| 🎙️ Real-time Voice | Ultra-low latency conversation in any language via Gemini Live API |

---

## 📦 Distribution & Packaging

### Running from Source
```bash
# 1. Install dependencies
py -m pip install -r requirements.txt

# 2. Launch
py main.py
```

### Building the Windows Desktop App
```bash
# Production windowed build (recommended)
.\build_windows.bat
# or via PowerShell:
.\scripts\build_windows.ps1

# Debug build (with console window for diagnosing startup issues)
.\scripts\build_windows.ps1 -Debug
```

The output executable is created at:
```
dist\AssistantWorker\AssistantWorker.exe
```

### Building the Windows Installer
Requires [Inno Setup 6](https://jrsoftware.org/isdl.php).
```bash
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\AssistantWorker.iss
```
Output: `installer\Output\AssistantWorker-Setup-1.0.0.exe`

### User Data Location
User settings, reminders, memory, and logs are stored in:
```
%LOCALAPPDATA%\AssistantWorker\
    ├── settings.json
    ├── reminders.json
    ├── history.json
    ├── memory\
    └── logs\
        └── assistant_worker.log
```
Bundled read-only assets in `dist\AssistantWorker\` are never modified at runtime.

### Troubleshooting
- **No window appears:** Check `%LOCALAPPDATA%\AssistantWorker\logs\assistant_worker.log` for details.
- **Audio fails to start:** Verify your input/output devices in Windows Sound Settings.
- **Wake word not detecting:** Ensure the model is installed from **⚙ → WAKE WORD** in the UI.

