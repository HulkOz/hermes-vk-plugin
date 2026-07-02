"""
VK Commands Menu v2 — полноценное меню команд Hermes Agent без LLM.

Архитектура:
  Уровень 0: Чат-клавиатура [📋 Команды] → TOC (Оглавление)
  Уровень 1: TOC с 5 кнопками категорий → страница категории
  Уровень 2: Страница категории (6 команд + навигация) → в LLM или след.стр.
  Уровень 3: Выбор команды → payload отправляет /cmd в агент (LLM)

Все навигационные действия — 0 токенов LLM.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

PER_PAGE = 6  # команд на странице категории

# ---------------------------------------------------------------------------
# Favorites storage
# ---------------------------------------------------------------------------

FAVORITES_FILE = os.path.expanduser("~/.hermes/plugins/vk/favorites.json")


def load_favorites() -> list[str]:
    """Load favorite command IDs from JSON file. Returns empty list on any error."""
    try:
        with open(FAVORITES_FILE, "r") as f:
            data = json.load(f)
            if isinstance(data, list):
                return [str(item) for item in data]
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return []


def save_favorites(ids: list[str]) -> None:
    """Save favorite command IDs to JSON file."""
    os.makedirs(os.path.dirname(FAVORITES_FILE), exist_ok=True)
    with open(FAVORITES_FILE, "w") as f:
        json.dump(ids, f, ensure_ascii=False, indent=2)
    logger.info("[Menu] Favorites saved: %s", ids)


def get_favorite_commands() -> list[MenuCommand]:
    """Return MenuCommand objects for favorite IDs, preserving order."""
    ids = load_favorites()
    lookup: dict[str, MenuCommand] = {}
    for cat in CATEGORIES.values():
        for cmd in cat.commands:
            lookup[cmd.id] = cmd
    return [lookup[fav_id] for fav_id in ids if fav_id in lookup]


def get_all_commands_flat() -> list[MenuCommand]:
    """Return all commands as a flat list in category order."""
    result: list[MenuCommand] = []
    for cat_id in CATEGORY_ORDER:
        cat = CATEGORIES.get(cat_id)
        if cat:
            result.extend(cat.commands)
    return result


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class MenuCommand:
    """Одна команда: id, label, emoji, цвет, описание."""
    id: str            # canonical name (без слэша)
    label: str         # кнопка: "/retry"
    emoji: str         # эмодзи
    color: str         # primary/secondary/negative/positive
    description: str   # подпись под кнопкой
    gateway: bool = True   # доступна в gateway


@dataclass
class MenuCategory:
    """Категория команд: id, label, эмодзи, список команд."""
    id: str
    label: str           # для кнопки в TOC
    emoji: str           # эмодзи категории
    description: str     # описание категории
    color: str           # цвет кнопки в TOC
    commands: list[MenuCommand] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Полный реестр команд из hermes_cli.commands.COMMAND_REGISTRY
# Сгруппированы по категориям. Все canonical names + все gateway-доступные.
# ---------------------------------------------------------------------------

CATEGORIES: dict[str, MenuCategory] = {}

SESSION = MenuCategory(
    id="session",
    label="Session",
    emoji="🧠",
    description="Управление сессией и историей",
    color="primary",
    commands=[
        MenuCommand("new",        "/new",        "🆕", "secondary", "Новая сессия (сброс)"),
        MenuCommand("reset",      "/reset",      "🆕", "secondary", "Новая сессия (алиас /new)"),
        MenuCommand("retry",      "/retry",      "🔄", "secondary", "Повторить последний ответ"),
        MenuCommand("undo",       "/undo",       "↩️", "secondary", "Отменить N обменов"),
        MenuCommand("title",      "/title",      "🏷️", "secondary", "Название сессии"),
        MenuCommand("topic",      "/topic",      "💬", "secondary", "Управление топиками Telegram"),
        MenuCommand("branch",     "/branch",     "🌿", "secondary", "Ветвление сессии"),
        MenuCommand("fork",       "/fork",       "🌿", "secondary", "Ветвление (алиас /branch)"),
        MenuCommand("compress",   "/compress",   "📦", "secondary", "Сжать контекст"),
        MenuCommand("rollback",   "/rollback",   "⏪", "secondary", "Откат чекпоинта"),
        MenuCommand("resume",     "/resume",     "▶️", "secondary", "Возобновить сессию"),
        MenuCommand("sessions",   "/sessions",   "📁", "secondary", "Список сессий"),
        MenuCommand("stop",       "/stop",       "⏹", "negative",  "Остановить фоновые процессы"),
        MenuCommand("approve",    "/approve",    "✅", "positive",  "Подтвердить опасную команду"),
        MenuCommand("deny",       "/deny",       "❌", "negative",  "Отклонить опасную команду"),
        MenuCommand("background", "/background", "⏳", "secondary", "Запустить в фоне"),
        MenuCommand("bg",         "/bg",         "⏳", "secondary", "Фон (алиас /background)"),
        MenuCommand("btw",        "/btw",        "⏳", "secondary", "Фон (алиас /background)"),
        MenuCommand("queue",      "/queue",      "📥", "secondary", "Поставить в очередь"),
        MenuCommand("q",          "/q",          "📥", "secondary", "Очередь (алиас /queue)"),
        MenuCommand("steer",      "/steer",      "🧭", "secondary", "Сообщение без прерывания"),
        MenuCommand("goal",       "/goal",       "🎯", "primary",   "Долгосрочная цель"),
        MenuCommand("agents",     "/agents",     "🤖", "secondary", "Активные агенты"),
        MenuCommand("tasks",      "/tasks",      "🤖", "secondary", "Агенты (алиас /agents)"),
        MenuCommand("moa",        "/moa",        "🔀", "secondary", "Mixture of Agents"),
        MenuCommand("subgoal",    "/subgoal",    "📌", "secondary", "Подцель для активной цели"),
        MenuCommand("status",     "/status",     "📊", "secondary", "Информация о сессии"),
        MenuCommand("profile",    "/profile",    "👤", "secondary", "Активный профиль"),
        MenuCommand("whoami",     "/whoami",     "🆔", "secondary", "Уровень доступа"),
        MenuCommand("sethome",    "/sethome",    "🏠", "secondary", "Домашний канал"),
        MenuCommand("set-home",   "/set-home",   "🏠", "secondary", "Дом.канал (алиас /sethome)"),
        MenuCommand("restart",    "/restart",    "🔄", "negative",  "Перезапуск gateway"),
    ],
)

CONFIGURATION = MenuCategory(
    id="config",
    label="Configuration",
    emoji="⚙️",
    description="Настройки и конфигурация",
    color="secondary",
    commands=[
        MenuCommand("model",       "/model",       "🧠", "primary",   "Показать/сменить модель"),
        MenuCommand("codex-runtime","/codex-runtime","🔧", "secondary","Режим Codex"),
        MenuCommand("codex_runtime","/codex_runtime","🔧", "secondary","Режим Codex (алиас)"),
        MenuCommand("personality", "/personality", "🎭", "secondary", "Выбрать личность"),
        MenuCommand("footer",      "/footer",      "📝", "secondary", "Мета-футер в ответах"),
        MenuCommand("yolo",        "/yolo",        "🔥", "negative",  "YOLO режим"),
        MenuCommand("reasoning",   "/reasoning",   "💭", "secondary", "Уровень рассуждений"),
        MenuCommand("fast",        "/fast",        "⚡", "primary",   "Fast Mode"),
        MenuCommand("voice",       "/voice",       "🎤", "secondary", "Голосовой режим"),
        MenuCommand("verbose",     "/verbose",     "🔉", "secondary", "Детализация прогресса"),
    ],
)

TOOLS = MenuCategory(
    id="tools",
    label="Tools & Skills",
    emoji="🧰",
    description="Инструменты, навыки, автоматизация",
    color="primary",
    commands=[
        MenuCommand("learn",       "/learn",       "📚", "primary",   "Обучить навык"),
        MenuCommand("memory",      "/memory",      "🧠", "secondary", "Просмотр/одобрение memory"),
        MenuCommand("suggestions", "/suggestions", "💡", "secondary", "Предложения автоматизаций"),
        MenuCommand("suggest",     "/suggest",     "💡", "secondary", "Алиас /suggestions"),
        MenuCommand("blueprint",   "/blueprint",   "📐", "secondary", "Шаблон автоматизации"),
        MenuCommand("bp",          "/bp",          "📐", "secondary", "Алиас /blueprint"),
        MenuCommand("curator",     "/curator",     "🔍", "secondary", "Фоновое улучшение навыков"),
        MenuCommand("kanban",      "/kanban",      "📋", "secondary", "Доска задач"),
        MenuCommand("bundles",     "/bundles",     "📦", "secondary", "Наборы навыков"),
        MenuCommand("reload-mcp",  "/reload-mcp",  "🔄", "secondary", "Перезагрузить MCP"),
        MenuCommand("reload_mcp",  "/reload_mcp",  "🔄", "secondary", "Алиас /reload-mcp"),
        MenuCommand("reload-skills","/reload-skills","🔄", "secondary","Перезагрузить навыки"),
        MenuCommand("reload_skills","/reload_skills","🔄", "secondary","Алиас /reload-skills"),
    ],
)

INFO = MenuCategory(
    id="info",
    label="Information",
    emoji="ℹ️",
    description="Справка и информация",
    color="secondary",
    commands=[
        MenuCommand("commands",    "/commands",    "📋", "primary",   "Список всех команд"),
        MenuCommand("help",        "/help",        "🆘", "primary",   "Помощь по командам"),
        MenuCommand("usage",       "/usage",       "📈", "secondary", "Статистика токенов"),
        MenuCommand("insights",    "/insights",    "🔍", "secondary", "Аналитика использования"),
        MenuCommand("credits",     "/credits",     "💰", "secondary", "Баланс и пополнение"),
        MenuCommand("update",      "/update",      "📥", "secondary", "Обновить Hermes"),
        MenuCommand("version",     "/version",     "📌", "secondary", "Версия Hermes"),
        MenuCommand("v",           "/v",           "📌", "secondary", "Версия (алиас /version)"),
        MenuCommand("debug",       "/debug",       "🐛", "negative",  "Диагностический отчёт"),
        MenuCommand("platform",    "/platform",    "📡", "secondary", "Статус платформы"),
    ],
)

CATEGORIES = {
    "session": SESSION,
    "config":  CONFIGURATION,
    "tools":   TOOLS,
    "info":    INFO,
}

CATEGORY_ORDER = ["session", "config", "tools", "info"]


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def get_toc_buttons() -> dict[str, Any]:
    """Inline-клавиатура для страницы Оглавления (TOC)."""
    buttons: list[list[dict]] = []
    row: list[dict] = []
    for i, cat_id in enumerate(CATEGORY_ORDER):
        cat = CATEGORIES[cat_id]
        btn = {
            "action": {
                "type": "text",
                "label": f"{cat.emoji} {cat.label}",
                "payload": json.dumps({"cmd": "cat", "cat": cat_id, "p": 1}, ensure_ascii=False),
            },
            "color": cat.color,
        }
        row.append(btn)
        if len(row) == 3 or i == len(CATEGORY_ORDER) - 1:
            buttons.append(row)
            row = []
    return {"buttons": buttons, "inline": True}


def get_toc_message() -> str:
    """Текст сообщения для страницы Оглавления."""
    lines = [
        "📋 **Оглавление команд**",
        "",
        "Выберите блок команд:",
        "",
    ]
    for cat_id in CATEGORY_ORDER:
        cat = CATEGORIES[cat_id]
        total_pages = _category_total_pages(cat_id)
        page_label = f" ({total_pages} стр.)" if total_pages > 1 else ""
        lines.append(f"  {cat.emoji} **{cat.label}** — {cat.description}{page_label}")
    lines.append("")
    lines.append("⬇️ Навигация — 0 токенов")
    return "\n".join(lines)


def _category_total_pages(cat_id: str) -> int:
    cat = CATEGORIES.get(cat_id)
    if not cat:
        return 1
    return max(1, (len(cat.commands) + PER_PAGE - 1) // PER_PAGE)


def _get_category_page_commands(cat_id: str, page: int) -> list[MenuCommand]:
    """Вернуть список команд для указанной страницы категории."""
    cat = CATEGORIES.get(cat_id)
    if not cat:
        return []
    total = _category_total_pages(cat_id)
    if page < 1:
        page = total
    elif page > total:
        page = 1
    start = (page - 1) * PER_PAGE
    end = start + PER_PAGE
    return cat.commands[start:end]


def get_category_buttons(cat_id: str, page: int = 1) -> dict[str, Any]:
    """Inline-клавиатура для страницы категории.

    Верхний ряд: команды (по 2 в ряд)
    Нижний ряд: [⬅️ Назад] [📋Оглавление] [➡️ Вперёд]
    """
    cat = CATEGORIES.get(cat_id)
    if not cat:
        return {"buttons": [], "inline": True}

    total = _category_total_pages(cat_id)
    cmds = _get_category_page_commands(cat_id, page)

    buttons: list[list[dict]] = []

    # Ряды команд — по 2 кнопки в ряд
    row: list[dict] = []
    for cmd in cmds:
        row.append({
            "action": {
                "type": "text",
                "label": f"{cmd.emoji} {cmd.label}",
                "payload": json.dumps({"cmd": cmd.id}, ensure_ascii=False),
            },
            "color": cmd.color,
        })
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    # Навигационный ряд — только нужные кнопки
    nav_row: list[dict] = []

    if page > 1:
        nav_row.append({
            "action": {
                "type": "text",
                "label": "⬅️ Назад",
                "payload": json.dumps({"cmd": "nav", "cat": cat_id, "p": page - 1}, ensure_ascii=False),
            },
            "color": "secondary",
        })

    nav_row.append({
        "action": {
            "type": "text",
            "label": "📋 Оглавление",
            "payload": json.dumps({"cmd": "toc"}, ensure_ascii=False),
        },
        "color": "primary",
    })

    if page < total:
        nav_row.append({
            "action": {
                "type": "text",
                "label": "Вперёд ➡️",
                "payload": json.dumps({"cmd": "nav", "cat": cat_id, "p": page + 1}, ensure_ascii=False),
            },
            "color": "primary",
        })

    buttons.append(nav_row)

    return {"buttons": buttons, "inline": True}


def get_category_message(cat_id: str, page: int = 1) -> str:
    """Текст сообщения для страницы категории."""
    cat = CATEGORIES.get(cat_id)
    if not cat:
        return "Категория не найдена"
    total = _category_total_pages(cat_id)
    cmds = _get_category_page_commands(cat_id, page)

    lines = [
        f"{cat.emoji} **{cat.label}** — {cat.description}",
        f"📄 Стр. {page}/{total}",
        "",
    ]
    for cmd in cmds:
        lines.append(f"  {cmd.emoji} `{cmd.label}` — {cmd.description}")
    lines.append("")
    lines.append("⬅️ / 📋 / ➡️ — 0 токенов   |   Выбор команды → в LLM")
    return "\n".join(lines)


def build_chat_keyboard() -> dict[str, Any]:
    """Чат-клавиатура под полем ввода — кнопки Команды и Избранное."""
    return {
        "one_time": False,
        "inline": False,
        "buttons": [[
            {
                "action": {
                    "type": "text",
                    "label": "📋 Команды",
                    "payload": json.dumps({"cmd": "toc"}, ensure_ascii=False),
                },
                "color": "primary",
            },
            {
                "action": {
                    "type": "text",
                    "label": "⭐ Избранное",
                    "payload": json.dumps({"cmd": "fav"}, ensure_ascii=False),
                },
                "color": "primary",
            },
        ]],
    }


def build_fav_keyboard() -> dict[str, Any]:
    """Inline-клавиатура для избранных команд + кнопка Настройка."""
    fav_cmds = get_favorite_commands()
    buttons: list[list[dict]] = []
    row: list[dict] = []
    for cmd in fav_cmds:
        row.append({
            "action": {
                "type": "text",
                "label": f"{cmd.emoji} {cmd.label}",
                "payload": json.dumps({"cmd": cmd.id}, ensure_ascii=False),
            },
            "color": cmd.color,
        })
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    # Кнопка настройки — всегда внизу
    buttons.append([{
        "action": {
            "type": "text",
            "label": "⚙️ Настройка",
            "payload": json.dumps({"cmd": "fav_setup"}, ensure_ascii=False),
        },
        "color": "secondary",
    }])
    return {"buttons": buttons, "inline": True}


def build_fav_setup_message() -> str:
    """Пронумерованный список всех доступных команд для настройки избранного."""
    all_cmds = get_all_commands_flat()
    lines = ["⚙️ **Настройка избранного**", ""]
    for i, cmd in enumerate(all_cmds, 1):
        lines.append(f"  {i}. {cmd.emoji} `{cmd.label}` — {cmd.description}")
    lines.append("")
    lines.append("Отправь **номера команд через запятую**, например: `1, 5, 12, 25`")
    lines.append("Команды появятся в том же порядке, в котором указаны номера.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Какие команды НЕ отправляются в LLM (обрабатываются локально 0 токенов)
# ---------------------------------------------------------------------------
_LOCAL_COMMANDS = {"toc", "cat", "nav", "commands", "fav", "fav_setup"}

# Все известные canonical id команд (для проверки "знаем ли мы эту команду")
_KNOWN_COMMANDS: set[str] = set()
for cat in CATEGORIES.values():
    for cmd in cat.commands:
        _KNOWN_COMMANDS.add(cmd.id)


def is_known_command(cmd_id: str) -> bool:
    """Проверить, известна ли команда по её canonical id."""
    return cmd_id in _KNOWN_COMMANDS


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

class MenuHandler:
    """Обработчик навигации по меню команд без LLM.

    В VK вызов происходит двумя путями:
      1. _process_update — text-кнопки (inline) с payload → handle() или замена текста
      2. handle_from_message — text-кнопка "📋 Команды" с chat-клавиатуры
    """

    def __init__(self, adapter=None):
        self._adapter = adapter
        self._awaiting_fav_config: set[int] = set()  # peer_ids ожидающие настройку избранного

    def set_adapter(self, adapter):
        self._adapter = adapter

    def is_menu_command(self, cmd: str) -> bool:
        """Команда обрабатывается локально (0 токенов)?"""
        return cmd in _LOCAL_COMMANDS

    def is_known_command(self, cmd_id: str) -> bool:
        """Известна ли команда по canonical id?"""
        return cmd_id in _KNOWN_COMMANDS

    async def handle(self, cmd: str, payload: dict[str, Any],
                     peer_id: int, event_id: str | None = None,
                     user_id: int | None = None) -> bool:
        """Обработать команду из payload callback-кнопки.

        Возвращает True, если команда обработана (выход, не отправлять в LLM).
        Возвращает False, если команда НЕ наша (пусть идёт в LLM).
        """
        # --- TOC: показать Оглавление ---
        if cmd in ("toc", "commands"):
            await self._send_toc(peer_id, event_id, user_id)
            return True

        # --- CAT: показать страницу категории ---
        if cmd == "cat":
            cat_id = payload.get("cat", "session")
            page = int(payload.get("p", 1))
            await self._send_category(peer_id, cat_id, page, event_id, user_id)
            return True

        # --- NAV: навигация внутри категории ---
        if cmd == "nav":
            cat_id = payload.get("cat", "session")
            page = int(payload.get("p", 1))
            await self._send_category(peer_id, cat_id, page, event_id, user_id)
            return True

        # --- FAV: показать избранное ---
        if cmd == "fav":
            await self._send_favorites(peer_id, event_id, user_id)
            return True

        # --- FAV_SETUP: настройка избранного ---
        if cmd == "fav_setup":
            await self._send_fav_setup(peer_id, event_id, user_id)
            return True

        # Не наша команда — пусть уходит в LLM
        return False

    async def handle_from_message(self, text: str, peer_id: int,
                                   event_id: str | None = None,
                                   user_id: int | None = None) -> tuple[bool, str]:
        """Обработать текстовое сообщение (нажатие на text-кнопку).

        Возвращает (handled, new_text):
          handled=True, new_text=""    → обработано, ничего не отправлять в LLM
          handled=True, new_text="/cmd" → обработано, отправить /cmd в LLM
          handled=False, new_text=text  → не наша команда, пусть LLM разбирается
        """
        t = text.strip()

        # --- fav_save: пользователь настроил избранное номерами ---
        if peer_id in self._awaiting_fav_config and re.match(r'^[\d,\s]+$', t):
            try:
                nums = [int(x.strip()) for x in t.split(",") if x.strip()]
                all_cmds = get_all_commands_flat()
                selected: list[str] = []
                for n in nums:
                    if 1 <= n <= len(all_cmds):
                        selected.append(all_cmds[n - 1].id)
                if selected:
                    save_favorites(selected)
                    self._awaiting_fav_config.discard(peer_id)
                    # Подтверждение
                    fav_cmds = get_favorite_commands()
                    labels = ", ".join(f"{cmd.emoji} {cmd.label}" for cmd in fav_cmds)
                    if self._adapter:
                        await self._adapter.send(
                            chat_id=str(peer_id),
                            content=f"✅ **Избранное сохранено:** {labels}",
                        )
                    # Показать кнопки избранного
                    await self._send_favorites(peer_id)
                    return True, ""
                else:
                    # Ни одной валидной команды — повторяем запрос
                    await self._send_fav_setup(peer_id, event_id, user_id)
                    return True, ""
            except ValueError:
                pass

        # Кнопка "📋 Команды" с chat-клавиатуры (с эмодзи и без)
        if t == "📋 Команды" or t == "Команды":
            await self._send_toc(peer_id, event_id, user_id)
            return True, ""

        # Кнопка "⭐ Избранное" с chat-клавиатуры
        if t == "⭐ Избранное" or t == "Избранное":
            await self._send_favorites(peer_id, event_id, user_id)
            return True, ""

        # Проверяем, не является ли текст известной командой
        # (для text-кнопок, которые могли быть нажаты на inline-клавиатуре)
        for cat in CATEGORIES.values():
            for cmd in cat.commands:
                # Сопоставляем по полному label (с эмодзи)
                expected = f"{cmd.emoji} {cmd.label}"
                if t == expected:
                    return True, cmd.label  # отправить /cmd в LLM

        return False, text

    # --- Приватные методы отправки --------------------------------------------------

    async def _send_favorites(self, peer_id: int,
                               event_id: str | None = None,
                               user_id: int | None = None) -> None:
        """Отправить сообщение с inline-кнопками избранных команд."""
        if not self._adapter:
            return
        fav_cmds = get_favorite_commands()
        if not fav_cmds:
            content = ("⭐ **Избранное**\n\n"
                       "У тебя пока нет избранных команд.\n"
                       "Нажми **⚙️ Настройка**, чтобы выбрать.")
            # Простая inline-клавиатура с одной кнопкой настройки
            kb = {
                "inline": True,
                "buttons": [[{
                    "action": {
                        "type": "text",
                        "label": "⚙️ Настройка",
                        "payload": json.dumps({"cmd": "fav_setup"}, ensure_ascii=False),
                    },
                    "color": "secondary",
                }]],
            }
            await self._answer_and_send(peer_id, content, kb, event_id, user_id)
        else:
            cmd_labels = [f"{cmd.emoji} {cmd.label}" for cmd in fav_cmds]
            lines = ["⭐ **Избранные команды**", ""]
            for label in cmd_labels:
                lines.append(f"• {label}")
            lines.append("")
            lines.append("⬇️ Нажми кнопку для вызова или ⚙️ для настройки")
            await self._answer_and_send(
                peer_id, "\n".join(lines), build_fav_keyboard(), event_id, user_id,
            )

    async def _send_fav_setup(self, peer_id: int,
                               event_id: str | None = None,
                               user_id: int | None = None) -> None:
        """Отправить пронумерованный список команд для настройки избранного."""
        if not self._adapter:
            return
        self._awaiting_fav_config.add(peer_id)
        content = build_fav_setup_message()
        # Пустая inline-клавиатура (убираем предыдущую)
        await self._answer_and_send(
            peer_id, content, {"buttons": [], "inline": True}, event_id, user_id,
        )

    async def _send_toc(self, peer_id: int,
                         event_id: str | None = None,
                         user_id: int | None = None) -> None:
        """Отправить TOC (Оглавление)."""
        if not self._adapter:
            return
        kb = get_toc_buttons()
        content = get_toc_message()
        await self._answer_and_send(peer_id, content, kb, event_id, user_id)

    async def _send_category(self, peer_id: int,
                              cat_id: str, page: int = 1,
                              event_id: str | None = None,
                              user_id: int | None = None) -> None:
        """Отправить страницу категории."""
        if not self._adapter:
            return
        kb = get_category_buttons(cat_id, page)
        content = get_category_message(cat_id, page)
        await self._answer_and_send(peer_id, content, kb, event_id, user_id)

    async def _answer_and_send(self, peer_id: int,
                                content: str,
                                keyboard: dict[str, Any],
                                event_id: str | None = None,
                                user_id: int | None = None) -> None:
        """Отправить сообщение с клавиатурой.

        Ответ на callback-событие (event_id) НЕ делаем здесь —
        он уже выполнен в _process_callback_event (adapter.py:1568).
        Повторный ответ на тот же event_id вызывает ошибку VK API 100:
        "invalid event_id" (VK разрешает ответить только один раз).
        """
        # Отправляем новое сообщение с клавиатурой
        try:
            await self._adapter.send(
                chat_id=str(peer_id),
                content=content,
                metadata={"keyboard": keyboard},
            )
        except Exception as e:
            logger.error("[Menu] Send failed: %s", e)

    async def send_chat_keyboard(self, peer_id: int) -> None:
        """Отправить приветственное сообщение с chat-клавиатурой."""
        if not self._adapter:
            return
        try:
            await self._adapter.send(
                chat_id=str(peer_id),
                content="✅ **Клавиатура активна**: 📋 Команды | ⭐ Избранное (0 токенов).",
                metadata={"keyboard": build_chat_keyboard()},
            )
        except Exception as e:
            logger.error("[Menu] Chat KB error: %s", e)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_handler: Optional[MenuHandler] = None


def get_handler() -> MenuHandler:
    global _handler
    if _handler is None:
        _handler = MenuHandler()
    return _handler
