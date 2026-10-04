# Assistant Worker

### AI Voice Assistant for Windows

Assistant Worker is a modern AI-powered Windows desktop assistant built with Python, PyQt6, and Gemini Live.

It supports natural voice conversations, real-time microphone feedback, Windows automation, reminders, system controls, application launching, and a modern conversation-focused desktop interface.

---

## Features

- **Gemini Live Voice Streaming:** Real-time conversational AI voice streaming with ultra-low latency.
- **Hybrid Cloud + Offline Mode:** Intelligent automatic fallback to local speech recognition and Windows SAPI5 speech synthesis when disconnected.
- **Modern 72/28 Split Layout:** Conversation panel on the left (~72%) with a dedicated voice interaction panel on the right (~28%).
- **VoiceOrb Visualization:** Dynamic, state-reactive audio visualization with real-time waveform and pulse feedback.
- **Live Microphone Input Meter:** 0–100% hardware-responsive audio meter tracking actual mic input.
- **Offline Model Management:** In-app download and storage management for Vosk and Whisper speech models under `%LOCALAPPDATA%\AssistantWorker\models\`.
- **Safety Confirmation Gates:** Critical operations (shutdown, restart) guarded by an on-screen confirmation banner.
- **Interrupt-to-Talk:** Seamless interruption handling—speak or press shortcut to interrupt the assistant instantly.
- **Desktop Automation:** Execute commands, launch applications, manipulate files, adjust volume, and check system stats.
- **Persistent Memory & Reminders:** Long-term conversation recall and scheduled reminder alerts.
- **System Tray Integration:** Minimize to tray, global shortcuts, live connection status tooltips, and single-instance protection.

---

## Hybrid Voice Architecture (Cloud + Offline Fallback)

Assistant Worker features a hybrid voice architecture designed for zero downtime:

### 1. Voice Modes
Configure your preferred mode under **⚙ Audio Devices**:
- **Automatic (Recommended):** Uses Gemini Live for cloud intelligence when connected, and gracefully falls back to local speech and system control when offline.
- **Cloud Only:** Strictly uses Gemini Live for cloud conversations.
- **Offline Only:** Operates entirely locally using offline speech recognition, local Windows TTS (SAPI5 via `pyttsx3`), and native OS controls.

### 2. Status Indicator States
The Voice Panel header and system tray tooltip provide real-time connection status:
- **`● CLOUD`** *(Green)*: Cloud voice active via Gemini Live WebSockets.
- **`● OFFLINE`** *(Amber)*: Offline mode active with local speech recognition and Windows system controls.
- **`● CONNECTING`** *(Cyan)*: Establishing connection with Gemini Live.
- **`● RECONNECTING`** *(Purple)*: Stepped exponential backoff retry (5s, 15s, 30s, 60s cap) with network flapping protection.

### 3. Offline Model Management
Manage local speech recognition models directly in the UI under **◈ Setup > 📥 Offline Models**:
- **Vosk English Small (~40 MB):** Ultra-lightweight streaming speech recognizer with minimal CPU footprint.
- **Whisper Tiny (~75 MB):** Fast offline speech transcription with int8 CPU quantization.
- **Whisper Base (~145 MB):** High-accuracy offline speech recognition.

Models are stored safely in `%LOCALAPPDATA%\AssistantWorker\models\` outside the application bundle. The manager includes:
- Live download progress bars and cancellation support.
- Integrity verification and disk usage reporting.
- Quick **Open Models Folder** shortcut to open the folder in Windows Explorer.

### 4. Fast Offline Intent Routing & Safety Gate
When offline, Assistant Worker responds to deterministic voice and typed commands:
- **Applications:** "open calculator", "launch chrome", "open vscode", "open downloads", "open notepad".
- **Hardware & System:** "check battery", "system status" (CPU and RAM usage), "current time", "today's date".
- **Volume Control:** "volume up", "volume down", "mute", "set volume to 60".
- **Safety Confirmation Gate:** Irreversible operations like "shut down computer" or "restart computer" require explicit user confirmation on the HUD banner before execution.
- **Duplicate Prevention:** Turn and request ID tracking combined with action cooldown timers prevent duplicate actions during network transitions.

### 5. Offline Startup Briefing
When starting without internet access, Assistant Worker delivers an adaptive local briefing—greeting the user, announcing the time, reporting battery percentage and power status, and verifying that local system controls are active—without timing out on web requests.

---

## Installation

### Recommended: Windows Installer
Download **`AssistantWorker-Setup-1.0.0.exe`** from [GitHub Releases (v1.0.0)](https://github.com/suragms/assistant-worker-ai/releases/tag/v1.0.0). Run the setup wizard to install Assistant Worker.

### Portable Version
Download **`AssistantWorker-1.0.0-Windows-x64.zip`** from [GitHub Releases (v1.0.0)](https://github.com/suragms/assistant-worker-ai/releases/tag/v1.0.0).

> **Important:** Extract the entire folder before running `AssistantWorker.exe`. Do not run or move the standalone executable without the `_internal` directory, as required libraries and assets reside there.

---

## Running from Source

Ensure Python 3.11+ is installed on Windows:

```powershell
git clone https://github.com/suragms/assistant-worker-ai.git
cd assistant-worker-ai
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
py main.py
```

---

## Known Voice Limitation

Production Assistant Worker speech uses Gemini Live.
The current Gemini Live API controls production speech rate, so the **Preview Speed** option applies only to EdgeTTS voice preview.

---

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl + Space` | Talk / Stop Listening |
| `Ctrl + M` | Microphone ON/OFF |
| `F4` | Microphone toggle |
| `Esc` | Stop listening / stop speaking |
| `F11` | Fullscreen toggle |

---

## Screenshots

### Assistant Worker
Main conversation interface with the right-side voice interaction panel.

### Voice Interaction
VoiceOrb, microphone level, transcription and voice controls.

*(Recommended future locations: `docs/screenshots/main-interface.png` and `docs/screenshots/voice-panel.png`)*

---

## Project Structure

```text
assistant-worker-ai/
├── actions/
├── config/
├── core/
├── dashboard/
├── installer/
├── memory/
├── plugins/
├── scripts/
├── widgets/
├── main.py
├── ui.py
├── requirements.txt
├── AssistantWorker.spec
└── README.md
```

---

## User Data Location

User configuration, preferences, long-term memory, and application logs are safely isolated in:

```text
%LOCALAPPDATA%\AssistantWorker\
├── config\
│   └── api_keys.json
├── memory\
│   └── long_term.json
└── logs\
    └── assistant_worker.log
```

---

## Author

**Surag Sunil**

GitHub: [@suragms](https://github.com/suragms)

---

## License

A license still needs to be selected for this repository.
