# Kalender

Omarchy shell calendar plugin by **kepeto**.

> Status: phase 2. The normalized event model, calendar event markers, agenda mode, and cache reader are implemented. Google OAuth/API and notification scheduling remain next.

## Planned features

- Localized date, weekday, month, and time formatting through the desktop Qt locale.
- Three panel modes: stock calendar, agenda, and hybrid calendar + agenda.
- Google Calendar sync through a separate local helper, keeping OAuth tokens outside QML.
- Notifications at 60, 30, 15, and 0 minutes before timed events.
- All-day event notification at 08:00 local time.
- 20-character event labels with an ellipsis.
- Configurable bounce-marquee animation on startup/restart and every 15 minutes.

## Current scaffold

- `manifest.json` — third-party Omarchy plugin manifest.
- `qml/BarWidget.qml` — forked clock bar widget with the new `kepeto.kalender` IPC identity.
- `qml/Panel.qml` — forked stock calendar panel, now using the configured Qt locale for labels.
- `qml/Model.js` — forked date/calendar logic.
- `docs/PLAN.md` — implementation plan, decisions, and open questions.
- `scripts/kalender-sync.py` — atomic normalized event-cache scaffold.

## Development

The plugin follows the current Omarchy plugin contract: a root `manifest.json` and QML entry point. Install or test locally with:

```bash
mkdir -p ~/.config/omarchy/plugins/kepeto.kalender
cp -a ./* ~/.config/omarchy/plugins/kepeto.kalender/
omarchy-shell shell rescanPlugins
omarchy plugin enable kepeto.kalender
omarchy bar put kepeto.kalender --section center

# Optional fixture cache for local UI testing
python3 scripts/kalender-sync.py --fixture config/events.example.json
```

Read the code before enabling it: Omarchy plugins execute unsandboxed inside the long-running `omarchy-shell` process.
