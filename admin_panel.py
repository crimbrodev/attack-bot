"""Интерактивная админка (inline-кнопки) — как у ZazyvalaTag2Bot.

В разрешённых группах — все настройки.
В остальных группах — только настройки зазывалы.
Доступ: админы группы (через Bot API getChatMember).
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode

from config import CHANNELS, ALLOWED_GROUPS
from storage import (
    load_groups, save_groups, get_remind_minutes, set_remind_minutes,
    is_attack_on, set_attack, set_channel_on,
    is_callall_on, set_callall,
    is_warnings_on, set_warnings,
    get_general_chat, set_general_chat,
    get_call_setting, set_call_setting,
)

router = Router()


async def _is_admin(cb: CallbackQuery) -> bool:
    """Проверяет является ли пользователь админом/создателем группы."""
    try:
        member = await cb.bot.get_chat_member(cb.message.chat.id, cb.from_user.id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False


def _is_allowed(chat_id: int) -> bool:
    return str(chat_id) in ALLOWED_GROUPS


# ═══════════════════════════════════════
#  ГЛАВНОЕ МЕНЮ
# ═══════════════════════════════════════

def _full_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Настройки зазывалы", callback_data="adm:zazyvala")],
        [InlineKeyboardButton(text="⚡ Настройки созыва", callback_data="adm:calls")],
        [InlineKeyboardButton(text="⚔️ Управление атаками", callback_data="adm:attacks")],
        [InlineKeyboardButton(text="⚙️ Другое", callback_data="adm:other")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="adm:close")],
    ])


def _zazyvala_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Настройки зазывалы", callback_data="adm:zazyvala")],
        [InlineKeyboardButton(text="⚡ Настройки созыва", callback_data="adm:calls")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="adm:close")],
    ])


@router.callback_query(F.data == "adm:menu")
async def cb_main_menu(cb: CallbackQuery):
    if not await _is_admin(cb):
        await cb.answer("Только для админов группы.", show_alert=True)
        return
    chat = cb.message.chat
    title = chat.title or chat.first_name or str(chat.id)
    kb = _full_menu_kb() if _is_allowed(chat.id) else _zazyvala_menu_kb()
    await cb.message.edit_text(
        f"⚙️ Настройки чата <b>{title}</b>:",
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
    )
    await cb.answer()


# ═══════════════════════════════════════
#  НАСТРОЙКИ ЗАЗЫВАЛЫ
# ═══════════════════════════════════════

WHO_OPTIONS = {"all": "Все", "admins": "Только админы"}

def _zazyvala_kb() -> InlineKeyboardMarkup:
    who_mute = get_call_setting("who_can_mute")
    who_call = get_call_setting("who_can_call")
    who_settings = get_call_setting("who_can_settings")
    auto_del = get_call_setting("auto_delete")
    del_delay = get_call_setting("delete_delay")
    msg_delay = get_call_setting("msg_delay")
    per_msg = get_call_setting("mentions_per_msg")

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"🔇 Кто может мутить себя: {WHO_OPTIONS.get(who_mute, who_mute)}",
            callback_data="adm:z:who_mute",
        )],
        [InlineKeyboardButton(
            text=f"📢 Кто может делать /callall: {WHO_OPTIONS.get(who_call, who_call)}",
            callback_data="adm:z:who_call",
        )],
        [InlineKeyboardButton(
            text=f"⚙️ Кто может открывать настройки: {WHO_OPTIONS.get(who_settings, who_settings)}",
            callback_data="adm:z:who_settings",
        )],
        [InlineKeyboardButton(
            text=f"🗑 Автоудаление сообщений созыва: {'✅ ВКЛ' if auto_del else '❌ ВЫКЛ'}",
            callback_data="adm:z:auto_delete",
        )],
        [InlineKeyboardButton(
            text=f"⏳ Задержка удаления: {del_delay} сек",
            callback_data="adm:z:del_delay",
        )],
        [InlineKeyboardButton(
            text=f"⏱ Задержка между сообщениями: {msg_delay} сек",
            callback_data="adm:z:msg_delay",
        )],
        [InlineKeyboardButton(
            text=f"🔢 Упоминаний в сообщении: {per_msg}",
            callback_data="adm:z:per_msg",
        )],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="adm:menu")],
    ])


@router.callback_query(F.data == "adm:zazyvala")
async def cb_zazyvala_menu(cb: CallbackQuery):
    if not await _is_admin(cb):
        await cb.answer("Только для админов группы.", show_alert=True)
        return
    await cb.message.edit_text(
        "📢 <b>Настройки зазывалы:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=_zazyvala_kb(),
    )
    await cb.answer()


# --- Кто может мутить себя ---
@router.callback_query(F.data == "adm:z:who_mute")
async def cb_z_who_mute(cb: CallbackQuery):
    if not await _is_admin(cb):
        await cb.answer("Только для админов группы.", show_alert=True)
        return
    current = get_call_setting("who_can_mute")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{'✅ ' if current == 'all' else ''}Все",
            callback_data="adm:z:who_mute:all",
        )],
        [InlineKeyboardButton(
            text=f"{'✅ ' if current == 'admins' else ''}Только админы",
            callback_data="adm:z:who_mute:admins",
        )],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="adm:zazyvala")],
    ])
    await cb.message.edit_text(
        "🔇 <b>Кто может мутить себя (выходить из призыва)?</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
    )
    await cb.answer()


@router.callback_query(F.data.startswith("adm:z:who_mute:"))
async def cb_z_who_mute_apply(cb: CallbackQuery):
    if not await _is_admin(cb):
        await cb.answer("Только для админов группы.", show_alert=True)
        return
    val = cb.data.split(":")[-1]
    set_call_setting("who_can_mute", val)
    await cb.answer(f"✅ Кто может мутить: {WHO_OPTIONS.get(val, val)}", show_alert=True)
    await cb_zazyvala_menu(cb)


# --- Кто может делать /callall ---
@router.callback_query(F.data == "adm:z:who_call")
async def cb_z_who_call(cb: CallbackQuery):
    if not await _is_admin(cb):
        await cb.answer("Только для админов группы.", show_alert=True)
        return
    current = get_call_setting("who_can_call")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{'✅ ' if current == 'all' else ''}Все",
            callback_data="adm:z:who_call:all",
        )],
        [InlineKeyboardButton(
            text=f"{'✅ ' if current == 'admins' else ''}Только админы",
            callback_data="adm:z:who_call:admins",
        )],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="adm:zazyvala")],
    ])
    await cb.message.edit_text(
        "📢 <b>Кто может делать /callall?</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
    )
    await cb.answer()


@router.callback_query(F.data.startswith("adm:z:who_call:"))
async def cb_z_who_call_apply(cb: CallbackQuery):
    if not await _is_admin(cb):
        await cb.answer("Только для админов группы.", show_alert=True)
        return
    val = cb.data.split(":")[-1]
    set_call_setting("who_can_call", val)
    await cb.answer(f"✅ Кто может делать /callall: {WHO_OPTIONS.get(val, val)}", show_alert=True)
    await cb_zazyvala_menu(cb)


# --- Кто может открывать настройки ---
@router.callback_query(F.data == "adm:z:who_settings")
async def cb_z_who_settings(cb: CallbackQuery):
    if not await _is_admin(cb):
        await cb.answer("Только для админов группы.", show_alert=True)
        return
    current = get_call_setting("who_can_settings")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{'✅ ' if current == 'all' else ''}Все",
            callback_data="adm:z:who_settings:all",
        )],
        [InlineKeyboardButton(
            text=f"{'✅ ' if current == 'admins' else ''}Только админы",
            callback_data="adm:z:who_settings:admins",
        )],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="adm:zazyvala")],
    ])
    await cb.message.edit_text(
        "⚙️ <b>Кто может открывать настройки зазывалы?</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
    )
    await cb.answer()


@router.callback_query(F.data.startswith("adm:z:who_settings:"))
async def cb_z_who_settings_apply(cb: CallbackQuery):
    if not await _is_admin(cb):
        await cb.answer("Только для админов группы.", show_alert=True)
        return
    val = cb.data.split(":")[-1]
    set_call_setting("who_can_settings", val)
    await cb.answer(f"✅ Кто может открывать настройки: {WHO_OPTIONS.get(val, val)}", show_alert=True)
    await cb_zazyvala_menu(cb)


# --- Автоудаление сообщений созыва ---
@router.callback_query(F.data == "adm:z:auto_delete")
async def cb_z_auto_delete(cb: CallbackQuery):
    if not await _is_admin(cb):
        await cb.answer("Только для админов группы.", show_alert=True)
        return
    current = get_call_setting("auto_delete")
    set_call_setting("auto_delete", not current)
    status = "✅ ВКЛ" if not current else "❌ ВЫКЛ"
    await cb.answer(f"Автоудаление сообщений созыва: {status}", show_alert=True)
    await cb_zazyvala_menu(cb)


# --- Задержка удаления ---
@router.callback_query(F.data == "adm:z:del_delay")
async def cb_z_del_delay(cb: CallbackQuery):
    if not await _is_admin(cb):
        await cb.answer("Только для админов группы.", show_alert=True)
        return
    variants = [0, 5, 10, 15, 30, 60, 120, 300]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{v} сек" if v > 0 else "Не удалять",
            callback_data=f"adm:z:del_delay:{v}",
        ) for v in variants[:4]],
        [InlineKeyboardButton(
            text=f"{v} сек",
            callback_data=f"adm:z:del_delay:{v}",
        ) for v in variants[4:]],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="adm:zazyvala")],
    ])
    await cb.message.edit_text(
        "⏳ <b>Задержка перед удалением сообщений созыва:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
    )
    await cb.answer()


@router.callback_query(F.data.startswith("adm:z:del_delay:"))
async def cb_z_del_delay_apply(cb: CallbackQuery):
    if not await _is_admin(cb):
        await cb.answer("Только для админов группы.", show_alert=True)
        return
    n = int(cb.data.split(":")[-1])
    set_call_setting("delete_delay", n)
    set_call_setting("auto_delete", n > 0)
    txt = f"✅ Задержка удаления: {n} сек" if n > 0 else "✅ Удаление отключено"
    await cb.answer(txt, show_alert=True)
    await cb_zazyvala_menu(cb)


# --- Задержка между сообщениями ---
@router.callback_query(F.data == "adm:z:msg_delay")
async def cb_z_msg_delay(cb: CallbackQuery):
    if not await _is_admin(cb):
        await cb.answer("Только для админов группы.", show_alert=True)
        return
    variants = [0.3, 0.5, 1, 2, 3, 5, 10]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{v} сек",
            callback_data=f"adm:z:msg_delay:{v}",
        ) for v in variants[:4]],
        [InlineKeyboardButton(
            text=f"{v} сек",
            callback_data=f"adm:z:msg_delay:{v}",
        ) for v in variants[4:]],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="adm:zazyvala")],
    ])
    await cb.message.edit_text(
        "⏱ <b>Задержка между сообщениями созыва:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
    )
    await cb.answer()


@router.callback_query(F.data.startswith("adm:z:msg_delay:"))
async def cb_z_msg_delay_apply(cb: CallbackQuery):
    if not await _is_admin(cb):
        await cb.answer("Только для админов группы.", show_alert=True)
        return
    v = float(cb.data.split(":")[-1])
    set_call_setting("msg_delay", v)
    await cb.answer(f"✅ Задержка между сообщениями: {v} сек", show_alert=True)
    await cb_zazyvala_menu(cb)


# --- Упоминаний в сообщении ---
@router.callback_query(F.data == "adm:z:per_msg")
async def cb_z_per_msg(cb: CallbackQuery):
    if not await _is_admin(cb):
        await cb.answer("Только для админов группы.", show_alert=True)
        return
    variants = [1, 2, 3, 5, 7, 10]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=str(v),
            callback_data=f"adm:z:per_msg:{v}",
        ) for v in variants[:3]],
        [InlineKeyboardButton(
            text=str(v),
            callback_data=f"adm:z:per_msg:{v}",
        ) for v in variants[3:]],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="adm:zazyvala")],
    ])
    await cb.message.edit_text(
        "🔢 <b>Сколько упоминаний в одном сообщении?</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
    )
    await cb.answer()


@router.callback_query(F.data.startswith("adm:z:per_msg:"))
async def cb_z_per_msg_apply(cb: CallbackQuery):
    if not await _is_admin(cb):
        await cb.answer("Только для админов группы.", show_alert=True)
        return
    n = int(cb.data.split(":")[-1])
    set_call_setting("mentions_per_msg", n)
    await cb.answer(f"✅ Упоминаний в сообщении: {n}", show_alert=True)
    await cb_zazyvala_menu(cb)


# ═══════════════════════════════════════
#  НАСТРОЙКИ СОЗЫВА (атаки)
# ═══════════════════════════════════════

def _calls_kb(cid: str) -> InlineKeyboardMarkup:
    g = load_groups()
    count = g.get(cid, {}).get("count", 5)
    remind = get_remind_minutes()
    autocall = "✅ ВКЛ" if is_callall_on() else "❌ ВЫКЛ"
    warnings = "✅ ВКЛ" if is_warnings_on() else "❌ ВЫКЛ"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📝 Черновиков на пост: {count}", callback_data="adm:setcount")],
        [InlineKeyboardButton(text=f"🔔 Напоминалка: каждые {remind} мин", callback_data="adm:remind")],
        [InlineKeyboardButton(text=f"📢 Авто-тег всех: {autocall}", callback_data="adm:autocall")],
        [InlineKeyboardButton(text=f"⚠️ Предупреждения взвода: {warnings}", callback_data="adm:warnings")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="adm:menu")],
    ])


@router.callback_query(F.data == "adm:calls")
async def cb_calls_menu(cb: CallbackQuery):
    if not await _is_admin(cb):
        await cb.answer("Только для админов группы.", show_alert=True)
        return
    cid = str(cb.message.chat.id)
    await cb.message.edit_text(
        "⚡ <b>Настройки созыва:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=_calls_kb(cid),
    )
    await cb.answer()


@router.callback_query(F.data == "adm:setcount")
async def cb_setcount_prompt(cb: CallbackQuery):
    if not await _is_admin(cb):
        await cb.answer("Только для админов группы.", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=str(i), callback_data=f"adm:setcount:{i}") for i in range(1, 6)],
        [InlineKeyboardButton(text=str(i), callback_data=f"adm:setcount:{i}") for i in range(6, 11)],
        [InlineKeyboardButton(text=str(i), callback_data=f"adm:setcount:{i}") for i in range(11, 16)],
        [InlineKeyboardButton(text=str(i), callback_data=f"adm:setcount:{i}") for i in range(16, 21)],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="adm:calls")],
    ])
    await cb.message.edit_text(
        "📝 <b>Сколько черновиков на пост?</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
    )
    await cb.answer()


@router.callback_query(F.data.startswith("adm:setcount:"))
async def cb_setcount_apply(cb: CallbackQuery):
    if not await _is_admin(cb):
        await cb.answer("Только для админов группы.", show_alert=True)
        return
    n = int(cb.data.split(":")[-1])
    g = load_groups()
    cid = str(cb.message.chat.id)
    if cid not in g:
        g[cid] = {"count": n, "title": cb.message.chat.title or cid}
    else:
        g[cid]["count"] = n
    save_groups(g)
    await cb.answer(f"✅ Теперь кидаю по {n} черновиков.", show_alert=True)
    cid = str(cb.message.chat.id)
    await cb.message.edit_text(
        "⚡ <b>Настройки созыва:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=_calls_kb(cid),
    )


@router.callback_query(F.data == "adm:remind")
async def cb_remind_prompt(cb: CallbackQuery):
    if not await _is_admin(cb):
        await cb.answer("Только для админов группы.", show_alert=True)
        return
    variants = [1, 2, 3, 5, 10, 15, 30, 60]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{m} мин", callback_data=f"adm:remind:{m}") for m in variants[:4]],
        [InlineKeyboardButton(text=f"{m} мин", callback_data=f"adm:remind:{m}") for m in variants[4:]],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="adm:calls")],
    ])
    await cb.message.edit_text(
        "🔔 <b>Интервал напоминалок:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
    )
    await cb.answer()


@router.callback_query(F.data.startswith("adm:remind:"))
async def cb_remind_apply(cb: CallbackQuery):
    if not await _is_admin(cb):
        await cb.answer("Только для админов группы.", show_alert=True)
        return
    n = int(cb.data.split(":")[-1])
    set_remind_minutes(n)
    await cb.answer(f"✅ Напоминалка каждые {n} мин.", show_alert=True)
    cid = str(cb.message.chat.id)
    await cb.message.edit_text(
        "⚡ <b>Настройки созыва:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=_calls_kb(cid),
    )


@router.callback_query(F.data == "adm:autocall")
async def cb_autocall_toggle(cb: CallbackQuery):
    if not await _is_admin(cb):
        await cb.answer("Только для админов группы.", show_alert=True)
        return
    on = not is_callall_on()
    set_callall(on)
    status = "✅ ВКЛ" if on else "❌ ВЫКЛ"
    await cb.answer(f"Авто-тег всех: {status}", show_alert=True)
    cid = str(cb.message.chat.id)
    await cb.message.edit_text(
        "⚡ <b>Настройки созыва:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=_calls_kb(cid),
    )


@router.callback_query(F.data == "adm:warnings")
async def cb_warnings_toggle(cb: CallbackQuery):
    if not await _is_admin(cb):
        await cb.answer("Только для админов группы.", show_alert=True)
        return
    on = not is_warnings_on()
    set_warnings(on)
    status = "✅ ВКЛ" if on else "❌ ВЫКЛ"
    await cb.answer(f"Предупреждения взвода: {status}", show_alert=True)
    cid = str(cb.message.chat.id)
    await cb.message.edit_text(
        "⚡ <b>Настройки созыва:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=_calls_kb(cid),
    )


# ═══════════════════════════════════════
#  УПРАВЛЕНИЕ АТАКАМИ (только разрешённые)
# ═══════════════════════════════════════

def _attacks_kb() -> InlineKeyboardMarkup:
    all_on = is_attack_on()
    buttons = []
    for ch in CHANNELS:
        ch_on = is_attack_on(ch)
        icon = "✅" if ch_on else "❌"
        buttons.append([InlineKeyboardButton(
            text=f"{icon} @{ch}",
            callback_data=f"adm:attack:{ch}",
        )])
    buttons.append([InlineKeyboardButton(
        text=f"{'🔴' if all_on else '🟢'} Всё {'выкл' if all_on else 'вкл'}",
        callback_data="adm:attack:all",
    )])
    buttons.append([InlineKeyboardButton(text="↩️ Назад", callback_data="adm:menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data == "adm:attacks")
async def cb_attacks_menu(cb: CallbackQuery):
    if not await _is_admin(cb):
        await cb.answer("Только для админов группы.", show_alert=True)
        return
    if not _is_allowed(cb.message.chat.id):
        await cb.answer("Атаки настраиваются только в основной группе.", show_alert=True)
        return
    await cb.message.edit_text(
        "⚔️ <b>Управление атаками:</b>\nНажми на канал чтобы вкл/выкл.",
        parse_mode=ParseMode.HTML,
        reply_markup=_attacks_kb(),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("adm:attack:"))
async def cb_attack_toggle(cb: CallbackQuery):
    if not await _is_admin(cb):
        await cb.answer("Только для админов группы.", show_alert=True)
        return
    if not _is_allowed(cb.message.chat.id):
        await cb.answer("Атаки настраиваются только в основной группе.", show_alert=True)
        return
    ch = cb.data.split(":")[-1]
    if ch == "all":
        new_state = not is_attack_on()
        set_attack(new_state)
        for c in CHANNELS:
            set_channel_on(c, new_state)
        status = "ВКЛ" if new_state else "ВЫКЛ"
        await cb.answer(f"Все атаки: {status}", show_alert=True)
    else:
        on = not is_attack_on(ch)
        set_channel_on(ch, on)
        status = "ВКЛ" if on else "ВЫКЛ"
        await cb.answer(f"@{ch}: {status}", show_alert=True)
    await cb_attacks_menu(cb)


# ═══════════════════════════════════════
#  ДРУГОЕ (только разрешённые)
# ═══════════════════════════════════════

def _other_kb() -> InlineKeyboardMarkup:
    general = get_general_chat() or "не задан"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💬 Чат уведомлений: {general}", callback_data="adm:setgeneral")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="adm:menu")],
    ])


@router.callback_query(F.data == "adm:other")
async def cb_other_menu(cb: CallbackQuery):
    if not await _is_admin(cb):
        await cb.answer("Только для админов группы.", show_alert=True)
        return
    if not _is_allowed(cb.message.chat.id):
        await cb.answer("Эти настройки только в основной группе.", show_alert=True)
        return
    await cb.message.edit_text(
        "⚙️ <b>Другие настройки:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=_other_kb(),
    )
    await cb.answer()


@router.callback_query(F.data == "adm:setgeneral")
async def cb_setgeneral_apply(cb: CallbackQuery):
    if not await _is_admin(cb):
        await cb.answer("Только для админов группы.", show_alert=True)
        return
    chat_id = str(cb.message.chat.id)
    set_general_chat(chat_id)
    await cb.answer(f"✅ Чат для уведомлений: {chat_id}", show_alert=True)
    await cb_other_menu(cb)


# ═══════════════════════════════════════
#  ЗАКРЫТЬ
# ═══════════════════════════════════════

@router.callback_query(F.data == "adm:close")
async def cb_close(cb: CallbackQuery):
    await cb.message.delete()
    await cb.answer()
