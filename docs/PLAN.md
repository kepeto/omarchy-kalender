# Kalender implementation plan

## 1. Product shape

**Kalender** is a fork-derived Omarchy bar widget. The bar label should remain compact and unambiguous:

`[calendar icon]  Thu 18 Sep 10:31  ·  ⏰ 12:40 Kuliah Bimo: Engl...`

The current time and the next event are separate visual segments. Event text is clipped to 20 Unicode-aware display characters and ends with `...` when shortened.

Panel modes:

1. **Calendar** — stock month grid, with event markers/counts.
2. **Agenda** — chronological event list around the selected date/range.
3. **Hybrid** — calendar on the left, agenda/details on the right; selecting a day filters the agenda and reveals event details.

The mode is persisted in the widget entry settings and can be changed from the panel or a future IPC method.

## 2. Architecture

### QML shell plugin

- Keep the plugin lightweight and compatible with the current Omarchy manifest contract.
- `BarWidget.qml` owns the compact bar label, marquee animation, settings, and IPC.
- `Panel.qml` owns the three presentation modes and selection state.
- `Model.js` remains pure date/event transformation logic so it can be tested without QML.
- Use `Qt.locale()` / the configured locale for all user-facing dates, months, weekdays, and time. Do not hard-code English labels except the default fallback UI strings.
- Use `Process` only for short-lived helper commands; never put OAuth or long-running network logic directly in the bar widget.

### Calendar sync helper

Implement a separate local helper under `scripts/` (initially Python or Node, choose based on available runtime) with:

- OAuth 2.0 Authorization Code flow using a loopback callback.
- Token cache under `${XDG_STATE_HOME:-$HOME/.local/state}/kalender/`, permissions `0700/0600`.
- Google Calendar API `events.list` with `singleEvents=true`, `orderBy=startTime`, bounded `timeMin/timeMax`, and incremental refresh interval.
- Normalized JSON cache written atomically, including `etag`, `updated`, `calendarId`, `eventId`, title, start/end, `allDay`, timezone, URL, and status.
- No client secret, refresh token, or access token in QML, git, logs, or shell.json.
- Graceful offline behavior: retain last successful cache and expose sync status/error to the panel.

The QML side should read the normalized cache through a small service or `FileView`-style binding appropriate to the installed Quickshell version. The helper can be triggered by a timer or a future IPC call; do not spawn a new network process every second.

## 3. Notifications

Notification scheduling must be idempotent and timezone-aware.

- Timed events: notify at `start - 60m`, `start - 30m`, `start - 15m`, and `start`.
- All-day events: notify at local 08:00 on the event date only.
- Never schedule timed offsets for all-day events.
- Use stable notification keys such as `calendarId:eventId:instanceStart:offset` to prevent duplicates after refresh/restart.
- Persist delivered keys and prune them after a configurable retention period.
- Handle edits, cancellations, recurring instances, DST transitions, missed notifications, and events whose start time is already in the past.
- Default policy: a missed pre-event notification is not replayed after startup; the 0-minute notification may be emitted only if it is still within a small configurable grace window.

The notification backend should use the desktop notification mechanism already available in Omarchy (prefer the existing shell/notification IPC contract if it exposes a stable call; otherwise use a dedicated notification command discovered during implementation). Verify exact API before coding.

## 4. Marquee / bounce

- The bar widget must not constantly animate or repaint.
- A configurable `marqueeEnabled` setting controls the feature.
- Trigger on plugin load/restart and then every 15 minutes by default (`marqueeIntervalMinutes: 15`).
- Use a bounded bounce animation: left-to-right, right-to-left, then settle. Stop it when there is no overflow or no event title.
- Debounce start/restart signals and use millisecond timestamps for interval checks.
- The text remains readable and never obscures the current-time segment.

## 5. Localization

- Date and time formatting follow `Qt.locale()` and the system's 12/24-hour convention where available.
- Month/day names come from the active locale.
- UI strings use a translation table with English as the default. Initial locale support should include English and a structure ready for Indonesian/Malay and other locales.
- Avoid passing empty or invalid locale strings to Qt formatting APIs; normalize locale settings and fall back safely.
- Respect locale first-day-of-week, with an explicit user override retained from the stock clock behavior.

## 6. Configuration proposal

Widget entry settings:

```json
{
  "id": "kepeto.kalender",
  "mode": "hybrid",
  "locale": "",
  "calendarIds": ["primary"],
  "syncIntervalMinutes": 5,
  "notificationsEnabled": true,
  "notifyMinutes": [60, 30, 15, 0],
  "allDayNotificationTime": "08:00",
  "eventTitleLimit": 20,
  "marqueeEnabled": true,
  "marqueeOnStart": true,
  "marqueeEveryMinutes": 15
}
```

Keep secrets and OAuth state out of this object.

## 7. Delivery phases

1. **Scaffold (current):** fork stock widget/panel/model, rename manifest/IPC, add docs, verify locale path.
2. **Domain model:** normalized event schema, clipping, date grouping, overlap/recurrence display, unit tests.
3. **Static agenda UI:** calendar, agenda, hybrid modes using fixture JSON.
4. **Sync helper:** OAuth, Google API, cache, refresh/error states.
5. **Notifications:** scheduler, persistence, all-day rule, idempotency, desktop integration.
6. **Bar polish:** next-event label, disambiguated now marker, marquee, settings.
7. **Integration QA:** shell reload, restart, timezone/DST, locale matrix, offline cache, recurring/all-day events, multi-monitor panel behavior.

## 8. Risks and improvements

- **OAuth complexity:** keep it outside QML and use a loopback browser flow; never embed credentials in the plugin.
- **Quickshell API drift:** verify against the installed Quickshell 0.3.1 and current Omarchy source before using newer APIs.
- **Notification duplication:** use persisted stable keys and atomic state writes.
- **Long/recurring events:** normalize Google event instances rather than treating recurrence strings in QML.
- **Locale edge cases:** test 12/24-hour formats, RTL locales, long month names, and DST boundaries.
- **Performance:** bounded fetch range, atomic cache replacement, one sync worker, and no per-second network/process work.
- **Security:** plugin code runs unsandboxed in `omarchy-shell`; sync credentials must be isolated and documented.

## References

- Omarchy shell plugin contract: <https://github.com/basecamp/omarchy/blob/master/shell/README.md>
- Omarchy plugin guide: <https://github.com/basecamp/omarchy/blob/master/manual/32-shell-plugins.md>
- Quickshell introduction: <https://quickshell.org/docs/guide/introduction/>
- Quickshell Process: <https://quickshell.org/docs/v0.3.1/types/Quickshell.Io/Process/>
- Google Calendar API reference: <https://developers.google.com/calendar/api/v3/reference>
- Google OAuth guidance: <https://developers.google.com/identity/protocols/oauth2>
