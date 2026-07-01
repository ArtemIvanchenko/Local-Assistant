"""Proactive jobs, scheduled on PTB's JobQueue (APScheduler under the hood).

Reminder state lives in SQLite, so polling survives restarts without a persistent
jobstore. Digests and the nightly reflection are cron-like and re-register on start.
"""

from __future__ import annotations

from datetime import time

from telegram.ext import Application, ContextTypes

from ..config import settings
from ..telegram.bot import reminder_keyboard
from ..util import in_quiet_hours, now, tz


def _parse_hhmm(s: str) -> time:
    h, m = (int(x) for x in s.split(":"))
    return time(hour=h, minute=m, tzinfo=tz())


def register(app: Application, deps) -> None:
    jq = app.job_queue

    def _cap_reached() -> bool:
        key = "proactive_" + now().strftime("%Y%m%d")
        return int(deps.db.get_setting(key, "0")) >= settings.max_proactive_per_day

    def _bump_cap() -> None:
        key = "proactive_" + now().strftime("%Y%m%d")
        deps.db.set_setting(key, str(int(deps.db.get_setting(key, "0")) + 1))

    async def broadcast(ctx: ContextTypes.DEFAULT_TYPE, text: str,
                        respect_quiet=True, respect_cap=True):
        if respect_quiet and in_quiet_hours():
            return
        if respect_cap and _cap_reached():
            return  # anti-spam: don't exceed MAX_PROACTIVE_PER_DAY
        for uid in settings.owner_ids:
            try:
                await ctx.bot.send_message(uid, text)
            except Exception:
                pass
        if respect_cap:
            _bump_cap()

    async def poll_reminders(ctx: ContextTypes.DEFAULT_TYPE):
        # Explicit reminders always fire — no quiet-hours / cap suppression.
        rows = deps.db.query(
            "SELECT id, text FROM reminders WHERE status='pending' AND fire_at<=? ",
            (now().isoformat(),),
        )
        for r in rows:
            for uid in settings.owner_ids:
                try:
                    await ctx.bot.send_message(
                        uid, f"⏰ {r['text']}", reply_markup=reminder_keyboard(r["id"])
                    )
                except Exception:
                    pass
            deps.db.execute("UPDATE reminders SET status='sent' WHERE id=?", (r["id"],))

    async def morning_digest(ctx: ContextTypes.DEFAULT_TYPE):
        events = await deps.tools.list_events(day="today")
        tasks = await deps.tools.list_tasks()
        await broadcast(ctx, f"☀️ Доброе утро!\n\nСегодня:\n{events}\n\nЗадачи:\n{tasks}")

    async def evening_digest(ctx: ContextTypes.DEFAULT_TYPE):
        tomorrow = await deps.tools.list_events(day="tomorrow")
        await broadcast(ctx, f"🌙 Итоги дня. Завтра:\n{tomorrow}")

    async def nightly_reflection(ctx: ContextTypes.DEFAULT_TYPE):
        try:
            await deps.reflect()
        except Exception:
            pass  # never let the nightly job crash the service

    async def icloud_sync(ctx: ContextTypes.DEFAULT_TYPE):
        try:
            await deps.sync_icloud()
        except Exception:
            pass  # transient iCloud/network errors must not kill the job

    jq.run_repeating(poll_reminders, interval=30, first=10)
    jq.run_daily(morning_digest, time=_parse_hhmm(settings.morning_digest))
    jq.run_daily(evening_digest, time=_parse_hhmm(settings.evening_digest))
    jq.run_daily(nightly_reflection, time=_parse_hhmm(settings.nightly_reflection))
    if settings.icloud_enabled:
        jq.run_repeating(icloud_sync, interval=settings.icloud_sync_minutes * 60, first=15)
