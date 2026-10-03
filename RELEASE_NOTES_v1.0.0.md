# Assistant Worker v1.0.0

Welcome to the first stable Windows release of **Assistant Worker**!

Assistant Worker is a personal AI desktop assistant designed specifically for Windows 10 and 11, combining natural Gemini Live voice interaction with rich desktop automation and system control.

---

## Highlights

- **Gemini Live Voice Conversations:** Real-time bi-directional voice streaming powered by Google Gemini Live API.
- **Modern 72/28 UI Layout:** Conversation thread on the left (~72%) paired with an interactive voice HUD on the right (~28%).
- **Hardware Microphone Meter:** Accurate real-time 0–100% audio level reactivity directly tracking your hardware microphone.
- **Interrupt-to-Talk:** Seamless voice interruption—speak or hit shortcuts to instantly halt assistant speech and start talking.
- **Dedicated Volume Control:** In-app Assistant audio volume slider with hardware level persistence.
- **Gemini Voice Selection:** Choose your preferred Gemini Live production voice profile directly in the voice panel.
- **EdgeTTS Voice Preview:** Offline voice auditions for testing alternative speech voices.
  *(Note: Production speech rate is governed by Gemini Live; preview speed controls EdgeTTS auditions).*
- **Windows Desktop Automation:** Native window management, media playback, screenshot analysis, and system navigation.
- **Application Launching:** Start applications, browser sessions, and workflow tools with natural voice prompts.
- **Battery & System Metrics:** Monitor live CPU, battery, and system telemetry from the UI.
- **Reminders & Memory:** Local long-term recall and background reminder notification daemon.
- **System Tray & Hotkeys:** Global push-to-talk shortcuts, tray minimization, and single-instance protection.
- **Start with Windows:** Seamless automatic launch with Windows logon option.
- **Persistent Settings:** Audio configurations, API preferences, and UI settings persist cleanly across application restarts.
- **Windows Installer & Portable ZIP:** Available as both an Inno Setup installer wizard and a standalone portable zip archive.

---

## Release Assets

| File | Description | SHA-256 Checksum |
|---|---|---|
| `AssistantWorker-Setup-1.0.0.exe` | Standard Windows Installer | `f0fc8d50ce725686edc658cbbd890aa78f8e3ac5c6fcdea21a12bae2f3fc24a6` |
| `AssistantWorker-1.0.0-Windows-x64.zip` | Portable Folder Archive | `738c0810edbf39b731d91cb76255eafcf750fabe6a2a765327e059e0f9969b47` |
| `SHA256SUMS.txt` | Checksum Verification File | Available in Release |

---

## Requirements

- **OS:** Windows 10 or Windows 11 (64-bit)
- **API Key:** Google Gemini API key (entered on first launch)
- **Audio:** Working microphone and speakers / headphones
