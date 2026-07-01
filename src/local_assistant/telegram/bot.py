"""Telegram front-end (python-telegram-bot v21, async).

Owner-only (chat_id whitelist). Slash commands are conveniences; free-form text goes
to the agent. Model selection is first-class: /models lists what's available, /model
switches the active main model at runtime.
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from ..config import settings
from ..llm.models import by_role, find
from ..util import now

EDIT_INTERVAL = 0.8  # seconds between Telegram message edits while streaming


def build_application(deps) -> Application:
    """deps: object with .llm .memory .tools .orchestrator .db"""
    app = Application.builder().token(settings.telegram_bot_token).build()
    app.bot_data["deps"] = deps

    def authorized(update: Update) -> bool:
        u = update.effective_user
        return bool(u and u.id in settings.owner_ids)

    # ── helpers ──────────────────────────────────────────────
    async def guard(update: Update) -> bool:
        if not authorized(update):
            return False
        return True

    # ── commands ─────────────────────────────────────────────
    async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not await guard(update):
            return
        await update.message.reply_text(
            "Привет! Я твой локальный ассистент-секретарь.\n"
            "Просто пиши обычным языком: «напомни завтра в 9 …», «что у меня сегодня».\n\n"
            "Команды: /today /tomorrow /tasks /note /search /models /model /help"
        )

    async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not await guard(update):
            return
        await update.message.reply_text(
            "/today, /tomorrow — события\n"
            "/tasks — открытые задачи\n"
            "/add <текст> — добавить задачу\n"
            "/done <текст> — закрыть задачу\n"
            "/note <текст> — запомнить факт\n"
            "/search <запрос> — поиск по памяти\n"
            "/contacts <имя> — найти в контактах Apple\n"
            "/models — доступные модели\n"
            "/model <имя> — выбрать основную модель"
        )

    async def today(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not await guard(update):
            return
        await update.message.reply_text(await deps.tools.list_events(day="today"))

    async def tomorrow(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not await guard(update):
            return
        await update.message.reply_text(await deps.tools.list_events(day="tomorrow"))

    async def tasks(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not await guard(update):
            return
        await update.message.reply_text(await deps.tools.list_tasks())

    async def add(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not await guard(update):
            return
        text = " ".join(ctx.args)
        if not text:
            await update.message.reply_text("Что добавить? /add <текст задачи>")
            return
        await update.message.reply_text(await deps.tools.add_task(title=text))

    async def done(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not await guard(update):
            return
        await update.message.reply_text(await deps.tools.complete_task(title=" ".join(ctx.args)))

    async def note(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not await guard(update):
            return
        await update.message.reply_text(await deps.tools.remember(content=" ".join(ctx.args)))

    async def search(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not await guard(update):
            return
        await update.message.reply_text(await deps.tools.search_memory(query=" ".join(ctx.args)))

    async def contacts(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not await guard(update):
            return
        if not ctx.args:
            await update.message.reply_text("Кого найти? /contacts <имя>")
            return
        await update.message.reply_text(await deps.tools.find_contact(name=" ".join(ctx.args)))

    # ── model selection ──────────────────────────────────────
    async def models(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not await guard(update):
            return
        installed = set(deps.llm.list_installed())
        active = deps.llm.main_model
        lines = [f"Активная основная модель: *{active}*", ""]
        for role, title in (("main", "Основные"), ("router", "Роутеры"), ("embed", "Эмбеддинги")):
            lines.append(f"*{title}:*")
            for m in by_role(role):
                mark = "✅" if any(i == m.name or i.startswith(m.name + ":") for i in installed) else "⬇️"
                star = " ⭐" if m.name == active else ""
                lines.append(f"{mark} `{m.name}` — {m.size}, tool-calling: {m.tool_calling}{star}")
            lines.append("")
        lines.append("Сменить: /model <имя>  ·  ✅ установлена, ⬇️ нужно `ollama pull`")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def model(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not await guard(update):
            return
        if not ctx.args:
            await update.message.reply_text(
                f"Текущая модель: {deps.llm.main_model}\nСменить: /model <имя> (см. /models)"
            )
            return
        name = ctx.args[0]
        if not deps.llm.is_installed(name):
            info = find(name)
            hint = f"\nЭто {info.notes}" if info else ""
            await update.message.reply_text(
                f"Модель `{name}` не установлена. Сначала: `ollama pull {name}`{hint}",
                parse_mode="Markdown",
            )
            return
        deps.llm.set_main_model(name)
        await update.message.reply_text(f"Готово. Основная модель теперь: {name}")

    # ── documents (RAG ingest) ───────────────────────────────
    async def on_document(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not await guard(update):
            return
        doc = update.message.document
        await ctx.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / doc.file_name
            f = await doc.get_file()
            await f.download_to_drive(str(dest))
            try:
                n = await deps.memory.ingest_document(str(dest), source=doc.file_name)
                await update.message.reply_text(f"Запомнил «{doc.file_name}» ({n} фрагментов).")
            except Exception as e:
                await update.message.reply_text(f"Не смог разобрать файл: {e}")

    # ── reminder snooze buttons ──────────────────────────────
    async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        q = update.callback_query
        if not (q.from_user and q.from_user.id in settings.owner_ids):
            await q.answer()
            return
        await q.answer()
        try:
            _, rid, action = q.data.split(":")
            rid = int(rid)
        except Exception:
            return
        if action == "done":
            deps.db.execute("UPDATE reminders SET status='done' WHERE id=?", (rid,))
            await q.edit_message_text(f"✓ {q.message.text.lstrip('⏰ ')}")
            return
        minutes = {"15": 15, "60": 60, "1440": 1440}.get(action, 15)
        from datetime import timedelta
        new_fire = now() + timedelta(minutes=minutes)
        deps.db.execute(
            "UPDATE reminders SET status='pending', fire_at=? WHERE id=?",
            (new_fire.isoformat(), rid),
        )
        await q.edit_message_text(
            f"⏰ отложено до {new_fire.strftime('%H:%M')} — {q.message.text.lstrip('⏰ ')}"
        )

    # ── free-form text → agent (streamed) ────────────────────
    async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not await guard(update):
            return
        await ctx.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
        sent = await update.message.reply_text("…")
        shown, partial, last_edit = "", "", 0.0
        try:
            async for partial in deps.orchestrator.handle_stream(update.message.text):
                t = time.monotonic()
                if partial and partial != shown and t - last_edit > EDIT_INTERVAL:
                    try:
                        await sent.edit_text(partial)
                    except Exception:
                        pass  # "message is not modified" / rate limits
                    shown, last_edit = partial, t
            final = partial or "…"
            if final != shown:
                await sent.edit_text(final)
        except Exception as e:
            await sent.edit_text(f"Ошибка: {e}. Проверь, запущен ли Ollama и скачана ли модель.")

    for name, fn in (
        ("start", start), ("help", help_cmd), ("today", today), ("tomorrow", tomorrow),
        ("tasks", tasks), ("add", add), ("done", done), ("note", note),
        ("search", search), ("contacts", contacts), ("models", models), ("model", model),
    ):
        app.add_handler(CommandHandler(name, fn))
    app.add_handler(CallbackQueryHandler(on_callback, pattern=r"^snz:"))
    app.add_handler(MessageHandler(filters.Document.ALL, on_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    return app


def reminder_keyboard(rid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("+15м", callback_data=f"snz:{rid}:15"),
        InlineKeyboardButton("+1ч", callback_data=f"snz:{rid}:60"),
        InlineKeyboardButton("Завтра", callback_data=f"snz:{rid}:1440"),
        InlineKeyboardButton("✓", callback_data=f"snz:{rid}:done"),
    ]])
