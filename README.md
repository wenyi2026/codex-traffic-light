# Codex Traffic Light

Unofficial desktop traffic-light status indicator for Codex on Windows.

Codex Traffic Light floats above the desktop and shows the current Codex state with three colors:

- **Green**: task completed, Codex is idle.
- **Yellow**: Codex is running, thinking, responding, or executing tools.
- **Red**: approval required, error, blocked state, or human intervention needed.

> This project is not an official OpenAI product.

## Features

- Always-on-top floating desktop widget.
- Dark and light UI modes.
- Minimize and close buttons.
- System tray menu in Chinese.
- Remembers the last selected theme and size.
- Starts with Codex through a lightweight watcher.
- Automatically closes when Codex fully exits.
- Detects Codex status from local session events first, then falls back to process activity.
- Includes a Windows installer package.

## Download

For normal users, download the latest installer from the GitHub Releases page:

```text
CodexTrafficLightInstaller-v1.2.0.exe
```

After installation, open Codex. The traffic-light window should appear automatically.

## Status Rules

| Color | State | Meaning | User Action |
| --- | --- | --- | --- |
| Green | Idle | No task is currently running. Codex is idle. | You can start a new task. |
| Yellow | Running | Codex is thinking, responding, executing tools, or running normally. | Wait for completion. |
| Red | Attention | Approval, error, blocked state, or human intervention is required. | Return to Codex and handle the request. |

## Local Paths

Installed files are placed under:

```text
%LOCALAPPDATA%\CodexTrafficLight
```

The startup watcher is placed under:

```text
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
```

## Build From Source

This project is implemented in Python and packaged for Windows with PyInstaller.

Recommended local build command:

```powershell
.\build-exe.cmd
```

Main source files:

- `codex_traffic_light.py`: main floating UI and status detection.
- `codex_traffic_light_watcher.py`: lightweight Codex startup watcher.
- `codex_traffic_light_installer.py`: Windows installer builder.
- `create_codex_traffic_light_manual.py`: user manual generator.

## Privacy

The app runs locally on your Windows machine. It reads local Codex session/status files to infer state and does not upload your data.

See [PRIVACY.md](PRIVACY.md) for details.

## License

MIT License. See [LICENSE](LICENSE).
