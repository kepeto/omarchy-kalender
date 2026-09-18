# Kalender

Omarchy shell calendar plugin by **kepeto**.

> Status: Google Calendar sync is implemented using a standard-library Python OAuth loopback flow. The normalized event model, calendar event markers, agenda mode, and cache reader are included. Notification scheduling remains next.

## Features

- Localized date, weekday, month, and time formatting through the desktop Qt locale.
- Three panel modes: stock calendar, agenda, and hybrid calendar + agenda.
- Google Calendar OAuth 2.0 loopback login with interactive Client ID and hidden Client Secret prompts.
- Timed and all-day event normalization, 20-character title clipping, and event markers.
- Atomic event cache under `~/.cache/kalender/events.json`.

## Files

- `manifest.json` — third-party Omarchy plugin manifest.
- `qml/BarWidget.qml` — compact bar widget and cache reader.
- `qml/Panel.qml` — calendar, agenda, and hybrid presentation.
- `qml/Model.js` — pure date and event transformation logic.
- `scripts/kalender-sync.py` — OAuth loopback sync, Calendar API fetch, normalization, and atomic cache writer.
- `docs/PLAN.md` — implementation plan and remaining work.

## Install

```bash
mkdir -p ~/.config/omarchy/plugins/kepeto.kalender
cp -a ./* ~/.config/omarchy/plugins/kepeto.kalender/
omarchy-shell shell rescanPlugins
omarchy plugin enable kepeto.kalender
omarchy bar put kepeto.kalender --section center
```

## Google Calendar OAuth

Create a Google Cloud OAuth client with application type **Desktop app** and enable the Google Calendar API. The tool accepts credentials interactively, so the secret is not placed in shell history:

```bash
python3 ~/.config/omarchy/plugins/kepeto.kalender/scripts/kalender-sync.py
```

It prompts for:

```text
Google OAuth Client ID:
Google OAuth Client secret:
Client secret entered: ...
```

The entered Client Secret is echoed once after input so you can verify that the pasted value was received correctly. Be aware that this makes the secret visible in the terminal scrollback.

It then opens the browser, starts a temporary loopback callback on `127.0.0.1`, saves the refresh token under `~/.local/state/kalender/token.json`, and writes normalized events to `~/.cache/kalender/events.json`.

For automation, pass the Client ID and secret explicitly, or use the legacy JSON file mode:

```bash
python3 scripts/kalender-sync.py \
  --client-id 'YOUR_CLIENT_ID.apps.googleusercontent.com' \
  --client-secret 'YOUR_CLIENT_SECRET'

python3 scripts/kalender-sync.py \
  --client-secret-file ~/.config/kalender/client_secret.json
```

Use `--reauthorize` to force a new consent flow. Do not commit credentials or token files.

## Fixture testing

```bash
python3 scripts/kalender-sync.py --help
cp config/events.google-calendar-demo.json ~/.cache/kalender/events.json
omarchy restart shell
```

Read the plugin code before enabling it: Omarchy plugins execute unsandboxed inside the long-running `omarchy-shell` process.
