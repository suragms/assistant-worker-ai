# Assistant Worker

### AI Voice Assistant for Windows

Assistant Worker is a modern AI-powered Windows desktop assistant built with Python, PyQt6, and Gemini Live.

It supports natural voice conversations, real-time microphone feedback, Windows automation, reminders, system controls, application launching, and a modern conversation-focused desktop interface.

---

## Features

- **Gemini Live Voice Streaming:** Real-time conversational AI voice streaming with ultra-low latency.
- **Modern 72/28 Split Layout:** Conversation panel on the left (~72%) with a dedicated voice interaction panel on the right (~28%).
- **VoiceOrb Visualization:** Dynamic, state-reactive audio visualization with real-time waveform and pulse feedback.
- **Live Microphone Input Meter:** 0–100% hardware-responsive audio meter tracking actual mic input.
- **Interrupt-to-Talk:** Seamless interruption handling—speak or press shortcut to interrupt the assistant instantly.
- **Desktop Automation:** Execute commands, launch applications, manipulate files, adjust volume, and check system stats.
- **Persistent Memory & Reminders:** Long-term conversation recall and scheduled reminder alerts.
- **System Tray Integration:** Minimize to tray, global shortcuts, and single-instance protection.

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
*(Expected screenshot path: `docs/screenshots/main-interface.png`)*

### Voice Interaction
VoiceOrb, microphone level, transcription and voice controls.
*(Expected screenshot path: `docs/screenshots/voice-panel.png`)*

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
