"""Proactive jobs, scheduled on PTB's JobQueue (APScheduler under the hood).

Reminder state lives in SQLite, so polling survives restarts without a persistent
jobstore. Digests and the nightly reflection are cron-like and re-register on start.
"""

from __future__ import annotations

from datetime import time

from telegram.ext import Application, ContextTypes

from ..config import settings
from ..util import in_quiet_hours, now, tz


def _parse_hhmm(s: str) -> time:
    h, m = (int(x) for x in s.split(":"))
    return time(hour=h, minute=m, tzinfo=tz())


def register(app: Application, deps) -> None:
    jq = app.job_queue

    async def broadcast(ctx: ContextTypes.DEFAULT_TYPE, text: str, respect_quiet=True):
        if respect_quiet and in_quiet_hours():
            return
        for uid in settings.owner_ids:
            try:
                await ctx.bot.send_message(uid, text)
            except Exception:
                pass

    async def poll_reminders(ctx: ContextTypes.DEFAULT_TYPE):
        rows = deps.db.query(
            "SELECT id, text FROM reminders WHERE status='pending' AND fire_at<=? ",
            (now().isoformat(),),
        )
        for r in rows:
            await broadcast(ctx, f"⏰ {r['text']}", respect_quiet=False)
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

    jq.run_repeating(poll_reminders, interval=30, first=10)
    jq.run_daily(morning_digest, time=_parse_hhmm(settings.morning_digest))
    jq.run_daily(evening_digest, time=_parse_hhmm(settings.evening_digest))
    jq.run_daily(nightly_reflection, time=_parse_hhmm(settings.nightly_reflection))
