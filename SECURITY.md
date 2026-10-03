# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability within Assistant Worker, please report it responsibly:

1. **Do NOT open a public GitHub issue** for sensitive security matters.
2. Email the maintainer directly at the contact address listed on the GitHub profile ([@suragms](https://github.com/suragms)).
3. Include detailed steps to reproduce the issue, along with relevant logs or environment details.

## Credential Handling

- Assistant Worker stores API credentials locally in `%LOCALAPPDATA%\AssistantWorker\config\api_keys.json`.
- Credentials are never transmitted to third parties other than the authenticated Google Gemini API endpoints.
- Remote control and phone pairing use local network encryption with one-time tokens and device verification.
