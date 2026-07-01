# Apple / iCloud integration

The assistant runs on Linux (the Pi), so it reaches Apple data through iCloud's open
protocols — **not** macOS local APIs. What works from Linux:

| Apple app | Protocol | Status |
|---|---|---|
| Calendar | CalDAV | ✅ read + write |
| Reminders | CalDAV (VTODO) | ✅ read + write |
| Contacts | CardDAV | ✅ read (search) |
| Mail | IMAP | not enabled (easy to add) |
| Notes / Messages / Photos | — | ❌ no open protocol from Linux |

## Setup

1. The data must be **synced to iCloud** (not "On My Mac" local calendars).
2. Generate an **app-specific password**: [appleid.apple.com](https://appleid.apple.com/)
   → Sign-In & Security → App-Specific Passwords → Generate. (Your normal Apple ID
   password will NOT work; the app-specific password bypasses 2FA.)
3. Put it in `.env`:
   ```
   APPLE_ID=you@icloud.com
   APPLE_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
   # optional — otherwise the first suitable calendar/list is used:
   ICLOUD_CALENDAR_NAME=Home
   ICLOUD_REMINDERS_LIST=Reminders
   ```
4. Verify: `python -m local_assistant --check` shows `icloud : on (...)`.

Leave `APPLE_ID` blank to disable and run fully local.

## How it behaves

- **Source of truth = iCloud** for calendar + reminders. Local SQLite is a **cache**
  so digests and lookups are fast and work offline.
- `add_event` / `add_reminder` **write through** to iCloud and cache locally. If iCloud
  is unreachable, they fall back to local-only and say so.
- A background job (`ICLOUD_SYNC_MINUTES`, default 15) pulls upcoming iCloud events and
  reminders into the cache, deduped by their iCloud UID (`ext_id`).
- `find_contact` / `/contacts <name>` searches iCloud contacts (CardDAV, read-only).

## Notes & limits

- CardDAV discovery is done live (principal → addressbook-home → first addressbook).
- Any iCloud/network error is caught and surfaced; it never crashes the assistant.
- Contacts are read-only for now; write support and iCloud Mail (IMAP) are natural
  follow-ups.
