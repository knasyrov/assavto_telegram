from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import Dispatcher
from api.client import APIClient

# Создаем API клиент
api_client = APIClient()

async def show_applications(call: CallbackQuery):
    """Отображает список заявок (первая страница)."""
    await show_applications_page(call, 1)

async def handle_applications_pagination(call: CallbackQuery):
    """Обрабатывает кнопки пагинации заявок."""
    page = int(call.data.split("_")[-1])  # Извлекаем номер страницы из callback_data
    await show_applications_page(call, page)

async def show_applications_page(call: CallbackQuery, page: int):
    """Отображает заявки для указанной страницы."""
    try:
        # Запрос к API
        applications_response = api_client.get_applications(call.from_user.id, page)
        applications = applications_response.get("data", [])
        total_pages = applications_response.get("total_pages", 1)
        current_page = applications_response.get("current_page", 1)

        if not applications:
            await call.message.edit_text("Заявки не найдены.")
            # Здесь замените на реальный вызов меню, если render_main_menu недоступен
            return

        # Формируем кнопки для заявок
        keyboard = InlineKeyboardMarkup()
        for application in applications:
            button_text = f"№{application['id']} | {application['status']} | {application['name']}"
            keyboard.add(InlineKeyboardButton(button_text, callback_data=f"application_{application['id']}"))

        # Добавляем кнопки пагинации
        if current_page > 1:
            keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data=f"applications_page_{current_page - 1}"))
        if current_page < total_pages:
            keyboard.add(InlineKeyboardButton("➡️ Вперёд", callback_data=f"applications_page_{current_page + 1}"))
        keyboard.add(InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_main_menu"))

        # Обновляем сообщение
        await call.message.edit_text(f"📄 Заявки (страница {current_page} из {total_pages}):", reply_markup=keyboard)
        await call.answer()
    except Exception as e:
        await call.message.edit_text(f"Произошла ошибка: {str(e)}")
        # Здесь замените на реальный вызов меню, если render_main_menu недоступен

async def show_application_details(call: CallbackQuery):
    """Отображает детали выбранной заявки."""
    application_id = int(call.data.split("_")[-1])
    try:
        # Получение информации о заявке
        application = api_client.get_application_details(call.from_user.id, application_id)
        if not application:
            await call.message.edit_text("Информация о заявке не найдена.")
            return

        # Формирование информации о заявке
        application_text = (
            f"<b>📄 Заявка №{application['id']}</b>\n\n"
            f"<b>Информация о заявке:</b>\n"
            f"📝 <b>Статус:</b> {application['status']}\n"
            f"📧 <b>Email:</b> {application['email'] or 'Не указан'}\n"
            f"📞 <b>Телефон:</b> {application['tel'] or 'Не указан'}\n"
            f"💬 <b>Комментарий:</b> {application['comment'] or 'Отсутствует'}\n"
            f"📅 <b>Создана:</b> {application['created']}\n"
        )

        # Формирование клавиатуры
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🔙 Назад к заявкам", callback_data=f"applications_page_1"))

        # Отправка информации
        await call.message.edit_text(application_text, reply_markup=keyboard, parse_mode="HTML")
        await call.answer()
    except Exception as e:
        await call.message.edit_text(f"Произошла ошибка: {str(e)}")

def register_handlers(dp: Dispatcher):
    """Регистрирует обработчики заявок."""
    dp.register_callback_query_handler(show_applications, lambda call: call.data == "applications")
    dp.register_callback_query_handler(handle_applications_pagination, lambda call: call.data.startswith("applications_page_"))
    dp.register_callback_query_handler(show_application_details, lambda call: call.data.startswith("application_"))