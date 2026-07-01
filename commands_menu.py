"""
VK Commands Menu — модуль для плагина hermes-vk-plugin.

Обрабатывает навигацию по меню команд Hermes Agent напрямую через VK API,
без вызова LLM агента. Экономит токены.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)

PER_PAGE = 6


@dataclass
class MenuCommand:
    id: str
    label: str
    color: str = "secondary"
    category: str = "hermes"
    description: str = ""


COMMANDS: list[MenuCommand] = [
    MenuCommand("help",       "🆘 /help",       "primary",   "hermes", "Справка по всем командам"),
    MenuCommand("retry",      "🔄 /retry",      "secondary", "hermes", "Повторить последний ответ"),
    MenuCommand("undo",       "↩️ /undo",       "secondary", "hermes", "Отменить последний обмен"),
    MenuCommand("new",        "🆕 /new",        "secondary", "hermes", "Новая сессия (сброс)"),
    MenuCommand("stop",       "⏹ /stop",       "negative",  "hermes", "Остановить фоновые процессы"),
    MenuCommand("status",     "📊 /status",     "secondary", "hermes", "Информация о сессии"),
    MenuCommand("usage",      "📈 /usage",      "secondary", "hermes", "Статистика токенов"),
    MenuCommand("model",      "🧠 /model",      "secondary", "hermes", "Показать/сменить модель"),
    MenuCommand("sethome",    "🏠 /sethome",    "secondary", "hermes", "Установить home-канал"),
    MenuCommand("insights",   "🔍 /insights",   "secondary", "hermes", "Аналитика использования"),
    MenuCommand("restart",    "🔄 /restart",    "negative",  "hermes", "Перезапустить gateway"),
]


def get_total_pages() -> int:
    return max(1, (len(COMMANDS) + PER_PAGE - 1) // PER_PAGE)


def get_page_commands(page: int) -> list[MenuCommand]:
    total = get_total_pages()
    if page < 1: page = total
    elif page > total: page = 1
    start = (page - 1) * PER_PAGE
    end = start + PER_PAGE
    return COMMANDS[start:end]


def build_inline_keyboard(page: int) -> dict[str, Any]:
    total_pages = get_total_pages()
    page = max(1, min(page, total_pages))
    cmds = get_page_commands(page)
    buttons: list[list[dict]] = []
    row: list[dict] = []
    for cmd in cmds:
        row.append({
            "action": {
                "type": "callback",
                "label": cmd.label,
                "payload": json.dumps({"cmd": cmd.id}, ensure_ascii=False),
            },
            "color": cmd.color,
        })
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    nav_row: list[dict] = []
    if page > 1:
        nav_row.append({
            "action": {
                "type": "text",
                "label": "⬅️ Назад",
                "payload": json.dumps({"cmd": "nav", "p": page - 1}, ensure_ascii=False),
            },
            "color": "secondary",
        })
    if page < total_pages:
        nav_row.append({
            "action": {
                "type": "text",
                "label": "Вперёд ➡️",
                "payload": json.dumps({"cmd": "nav", "p": page + 1}, ensure_ascii=False),
            },
            "color": "primary",
        })
    if nav_row:
        buttons.append(nav_row)
    return {"buttons": buttons, "inline": True}


def build_chat_keyboard() -> dict[str, Any]:
    return {
        "one_time": False,
        "inline": False,
        "buttons": [[{
            "action": {
                "type": "text",
                "label": "📋 Команды",
                "payload": json.dumps({"cmd": "commands"}, ensure_ascii=False),
            },
            "color": "primary",
        }]],
    }


_LOCAL_COMMANDS = {"commands", "nav"}


class MenuHandler:
    def __init__(self, adapter=None):
        self._adapter = adapter

    def set_adapter(self, adapter):
        self._adapter = adapter

    def is_menu_command(self, cmd: str) -> bool:
        return cmd in _LOCAL_COMMANDS

    async def handle(self, cmd: str, payload: dict[str, Any],
                     peer_id: int, event_id: str | None = None,
                     user_id: int | None = None) -> bool:
        if cmd == "commands":
            await self._send_page(peer_id, 1, event_id, user_id)
            return True
        if cmd == "nav":
            page = int(payload.get("p", 1))
            await self._send_page(peer_id, page, event_id, user_id)
            return True
        return False

    async def handle_from_message(self, text: str, peer_id: int,
                                   event_id: str | None = None,
                                   user_id: int | None = None) -> tuple[bool, str]:
        t = text.strip()
        if t == "📋 Команды":
            await self._send_page(peer_id, 1, event_id, user_id)
            return True, ""
        if t in ("⬅️ Назад", "Вперёд ➡️"):
            await self._send_page(peer_id, 1, event_id, user_id)
            return True, ""
        for mc in COMMANDS:
            if t == mc.label:
                return True, f"/{mc.id}"
        return False, text

    async def _send_page(self, peer_id: int, page: int = 1,
                          event_id: str | None = None,
                          user_id: int | None = None) -> None:
        if not self._adapter:
            return
        total = get_total_pages()
        kb = build_inline_keyboard(page)
        lines = ["📋 **Команды Hermes Agent**", "", f"Страница {page}/{total}:"]
        for cmd in get_page_commands(page):
            lines.append(f"  {cmd.label} — {cmd.description}")
        lines.append("")
        lines.append("⬅️ / ➡️ — без траты токенов")
        content = "\n".join(lines)
        if event_id and hasattr(self._adapter, '_answer_callback_event'):
            try:
                await self._adapter._answer_callback_event(event_id, peer_id, user_id)
            except Exception:
                pass
        try:
            await self._adapter.send(
                chat_id=str(peer_id), content=content, metadata={"keyboard": kb},
            )
        except Exception as e:
            logger.error("[Menu] Failed: %s", e)

    async def send_chat_keyboard(self, peer_id: int) -> None:
        if not self._adapter:
            return
        try:
            await self._adapter.send(
                chat_id=str(peer_id),
                content="✅ **Команды** — нажми для списка (без траты токенов).",
                metadata={"keyboard": build_chat_keyboard()},
            )
        except Exception as e:
            logger.error("[Menu] Chat KB error: %s", e)


_handler: Optional[MenuHandler] = None


def get_handler() -> MenuHandler:
    global _handler
    if _handler is None:
        _handler = MenuHandler()
    return _handler
