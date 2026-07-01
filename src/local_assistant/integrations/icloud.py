"""Apple iCloud integration over open protocols (works from Linux/Pi).

- Calendar + Reminders via CalDAV (`caldav` library); reminders are VTODO items.
- Contacts via CardDAV (minimal httpx client + vobject parsing, read-only).

Auth uses an app-specific password from appleid.apple.com (bypasses 2FA). All calls
are synchronous; callers wrap them in asyncio.to_thread. Every public method is
defensive — on any failure it raises a clear error the caller can surface, so iCloud
problems never crash the assistant (the local SQLite path remains the fallback).
"""

from __future__ import annotations

from datetime import datetime, timedelta

import httpx

from ..config import settings
from ..util import now


class ICloudCalendar:
    """CalDAV-backed calendar + reminders."""

    def __init__(self):
        self._principal = None
        self._cal = None   # events calendar
        self._todos = None  # reminders list

    def _connect(self):
        if self._principal is not None:
            return
        import caldav  # lazy

        client = caldav.DAVClient(
            url=settings.icloud_caldav_url,
            username=settings.apple_id,
            password=settings.apple_app_password,
        )
        self._principal = client.principal()
        self._pick_calendars()

    def _pick_calendars(self):
        cals = self._principal.calendars()
        want_cal = settings.icloud_calendar_name.strip().lower()
        want_todo = settings.icloud_reminders_list.strip().lower()
        for c in cals:
            try:
                comps = set(c.get_supported_components())
            except Exception:
                comps = set()
            name = (c.name or "").lower()
            if "VEVENT" in comps:
                if (want_cal and name == want_cal) or (not want_cal and self._cal is None):
                    self._cal = c
            if "VTODO" in comps:
                if (want_todo and name == want_todo) or (not want_todo and self._todos is None):
                    self._todos = c

    # ── events ───────────────────────────────────────────────
    def add_event(self, title: str, start: datetime, end: datetime | None = None,
                  notes: str | None = None) -> str:
        self._connect()
        if self._cal is None:
            raise RuntimeError("no iCloud calendar that supports events")
        end = end or (start + timedelta(hours=1))
        ev = self._cal.save_event(
            dtstart=start, dtend=end, summary=title,
            description=notes or "",
        )
        return ev.icalendar_component.get("uid", "")

    def list_events(self, start: datetime | None = None, days: int = 30) -> list[dict]:
        self._connect()
        if self._cal is None:
            return []
        start = start or now()
        found = self._cal.search(
            start=start, end=start + timedelta(days=days), event=True, expand=True
        )
        out = []
        for ev in found:
            comp = ev.icalendar_component
            dt = comp.get("dtstart")
            out.append({
                "uid": str(comp.get("uid", "")),
                "title": str(comp.get("summary", "")),
                "start": dt.dt.isoformat() if dt else "",
            })
        return sorted(out, key=lambda x: x["start"])

    # ── reminders (VTODO) ────────────────────────────────────
    def add_reminder(self, text: str, due: datetime) -> str:
        self._connect()
        if self._todos is None:
            raise RuntimeError("no iCloud reminders list available")
        todo = self._todos.save_todo(summary=text, due=due)
        return todo.icalendar_component.get("uid", "")

    def list_reminders(self) -> list[dict]:
        self._connect()
        if self._todos is None:
            return []
        out = []
        for t in self._todos.todos():
            comp = t.icalendar_component
            due = comp.get("due")
            out.append({
                "uid": str(comp.get("uid", "")),
                "text": str(comp.get("summary", "")),
                "due": due.dt.isoformat() if due else "",
            })
        return out


class ICloudContacts:
    """Minimal read-only CardDAV client for iCloud contacts."""

    _NS = {"d": "DAV:", "card": "urn:ietf:params:xml:ns:carddav"}

    def __init__(self):
        self._addressbook_url: str | None = None
        self._auth = (settings.apple_id, settings.apple_app_password)

    def _client(self) -> httpx.Client:
        return httpx.Client(auth=self._auth, follow_redirects=True, timeout=20,
                            headers={"User-Agent": "local-assistant"})

    def _discover(self):
        if self._addressbook_url:
            return
        import xml.etree.ElementTree as ET

        with self._client() as c:
            base = settings.icloud_carddav_url.rstrip("/")
            # 1. current-user-principal
            r = c.request("PROPFIND", base + "/", headers={"Depth": "0"}, content=(
                '<d:propfind xmlns:d="DAV:"><d:prop>'
                "<d:current-user-principal/></d:prop></d:propfind>"
            ))
            root = ET.fromstring(r.text)
            href = root.find(".//d:current-user-principal/d:href", self._NS)
            principal = httpx.URL(base).join(href.text) if href is not None else base
            # 2. addressbook-home-set
            r = c.request("PROPFIND", str(principal), headers={"Depth": "0"}, content=(
                '<d:propfind xmlns:d="DAV:" xmlns:card="urn:ietf:params:xml:ns:carddav">'
                "<d:prop><card:addressbook-home-set/></d:prop></d:propfind>"
            ))
            root = ET.fromstring(r.text)
            home = root.find(".//card:addressbook-home-set/d:href", self._NS)
            home_url = httpx.URL(str(principal)).join(home.text)
            # 3. first addressbook collection under home
            r = c.request("PROPFIND", str(home_url), headers={"Depth": "1"}, content=(
                '<d:propfind xmlns:d="DAV:"><d:prop>'
                "<d:resourcetype/></d:prop></d:propfind>"
            ))
            root = ET.fromstring(r.text)
            for resp in root.findall(".//d:response", self._NS):
                if resp.find(".//card:addressbook", self._NS) is not None:
                    self._addressbook_url = str(httpx.URL(str(home_url)).join(
                        resp.find("d:href", self._NS).text))
                    break

    def search(self, query: str, limit: int = 10) -> list[dict]:
        import vobject

        self._discover()
        if not self._addressbook_url:
            raise RuntimeError("could not locate iCloud addressbook")
        with self._client() as c:
            r = c.request("REPORT", self._addressbook_url, headers={"Depth": "1"}, content=(
                '<card:addressbook-query xmlns:d="DAV:" '
                'xmlns:card="urn:ietf:params:xml:ns:carddav"><d:prop>'
                "<card:address-data/></d:prop></card:addressbook-query>"
            ))
        import xml.etree.ElementTree as ET

        root = ET.fromstring(r.text)
        q = query.lower().strip()
        out: list[dict] = []
        for data in root.findall(".//card:address-data", self._NS):
            if not data.text:
                continue
            try:
                card = vobject.readOne(data.text)
            except Exception:
                continue
            name = str(getattr(card, "fn", "").value) if hasattr(card, "fn") else ""
            if q and q not in name.lower():
                continue
            phones = [t.value for t in card.contents.get("tel", [])]
            emails = [e.value for e in card.contents.get("email", [])]
            out.append({"name": name, "phones": phones, "emails": emails})
            if len(out) >= limit:
                break
        return out


def calendar() -> ICloudCalendar:
    return ICloudCalendar()


def contacts() -> ICloudContacts:
    return ICloudContacts()
