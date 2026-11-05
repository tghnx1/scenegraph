"""Progress reports for the explicitly selected local classification snapshot."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass

import psycopg

from app.supervisor.telegram import TelegramBotApi


@dataclass(frozen=True, slots=True)
class Progress:
    total: int
    succeeded: int
    failed: int


def read_progress(connection: psycopg.Connection, run_ids: list[int]) -> Progress:
    total, succeeded, failed = connection.execute("""
        SELECT count(*), count(*) FILTER (WHERE status = 'succeeded'),
               count(*) FILTER (WHERE status = 'failed')
        FROM promoter_role_backfill_item WHERE run_id = ANY(%s)
    """, (run_ids,)).fetchone()
    connection.commit()
    return Progress(total, succeeded, failed)


def format_progress(before: Progress, after: Progress, status: str) -> str:
    processed = max(0, after.succeeded - before.succeeded)
    remaining = max(0, after.total - after.succeeded)
    percent = 100 * after.succeeded / after.total if after.total else 0
    if remaining == 0:
        estimate = "0"
    elif processed:
        estimate = f"около {math.ceil(remaining / processed)} при такой же скорости"
    else:
        estimate = "пока нельзя оценить: за этот проход нет новых результатов"
    reason = {"paused": "пауза, причина в журнале", "succeeded": "партия завершена",
              "failed": "партия завершилась с ошибками", "quota": "ожидание квоты Kimi"}.get(status, status)
    return (f"Локальная классификация промоутеров — {reason}\n"
            f"До прохода: {before.succeeded} из {after.total}\n"
            f"Обработано за проход: {processed}\n"
            f"Готово всего: {after.succeeded} из {after.total} ({percent:.1f}%)\n"
            f"Осталось: {remaining}; из них ошибок: {after.failed}\n"
            f"Оставшиеся проходы: {estimate}")


def notify_progress(message: str) -> None:
    token = os.environ.get("SUPERVISOR_TELEGRAM_BOT_TOKEN", "").strip()
    chats = [chat.strip() for chat in os.environ.get("SUPERVISOR_TELEGRAM_CHAT_IDS", "").split(",") if chat.strip()]
    if not token or not chats:
        print("telegram_notification_not_configured", flush=True)
        return
    bot = TelegramBotApi(token)
    for chat in chats:
        try:
            bot.send(message, chat_id=chat)
        except Exception:
            # The exception may contain a token-bearing URL; never include it in logs.
            print("telegram_notification_failed", flush=True)
