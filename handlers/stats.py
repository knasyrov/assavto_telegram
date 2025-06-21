from aiogram import Dispatcher
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from api.client import APIClient
from datetime import datetime, timedelta

api_client = APIClient()

# Команда /stats
async def show_stats_menu(message_or_call):
    """Показывает меню с диапазонами для статистики."""
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("📅 Текущий месяц", callback_data="current_month"))
    keyboard.add(InlineKeyboardButton("📅 Последние 2 месяца", callback_data="last_2_months"))
    keyboard.add(InlineKeyboardButton("📅 Последние 3 месяца", callback_data="last_3_months"))
    keyboard.add(InlineKeyboardButton("📅 Последние 6 месяцев", callback_data="last_6_months"))
    keyboard.add(InlineKeyboardButton("📅 За год", callback_data="last_year"))
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="back_to_main_menu"))

    if isinstance(message_or_call, CallbackQuery):
        await message_or_call.message.edit_text("Выберите временной диапазон для статистики:", reply_markup=keyboard)
        await message_or_call.answer()  # Убирает "загрузка..." в Telegram
    elif isinstance(message_or_call, Message):
        await message_or_call.answer("Выберите временной диапазон для статистики:", reply_markup=keyboard)

# Обработка диапазонов
async def process_stats_choice(call: CallbackQuery):
    """Обрабатывает выбор временного диапазона."""
    choice = call.data
    today = datetime.today()

    # Определяем начальную и конечную даты на основе выбранного диапазона
    if choice == "current_month":
        start_date = today.replace(day=1).strftime('%Y-%m-%d')
    elif choice == "last_2_months":
        start_date = (today - timedelta(days=60)).replace(day=1).strftime('%Y-%m-%d')
    elif choice == "last_3_months":
        start_date = (today - timedelta(days=90)).replace(day=1).strftime('%Y-%m-%d')
    elif choice == "last_6_months":
        start_date = (today - timedelta(days=180)).replace(day=1).strftime('%Y-%m-%d')
    elif choice == "last_year":
        start_date = today.replace(year=today.year - 1, day=1).strftime('%Y-%m-%d')
    else:
        await call.message.answer("Неверный выбор. Попробуйте снова.")
        await call.answer()
        return

    end_date = today.strftime('%Y-%m-%d')

    try:
        dashboard = api_client.get_dashboard(call.message.chat.id, start_date, end_date)
        if not dashboard:
            await call.message.answer("Не удалось получить данные статистики. Попробуйте позже.")
            return

        indicators = dashboard.get("indicators", [])
        response = f"📊 Статистика с {start_date} по {end_date}:\n"
        for indicator in indicators:
            response += f"- {indicator['name']}: {indicator['value']}\n"

        # Удаляем старое меню и отправляем статистику
        await call.message.delete()
        await call.message.answer(response)

        from app import render_main_menu
        # Отображаем обновлённое меню
        await render_main_menu(call.message, call.from_user.id)

    except Exception as e:
        await call.message.answer(f"Произошла ошибка: {str(e)}")
        await call.answer()

def register_handlers(dp: Dispatcher):
    dp.register_callback_query_handler(show_stats_menu, lambda call: call.data == "stats")
    dp.register_callback_query_handler(process_stats_choice, lambda call: call.data in ["current_month", "last_2_months", "last_3_months", "last_6_months", "last_year"])