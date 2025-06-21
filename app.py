from aiogram import Bot, Dispatcher, executor
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiohttp import web
from config.settings import BOT_TOKEN
from utils.db import init_db, add_user, remove_user, is_user_authorized, get_authorized_users
import asyncio
from api.client import APIClient
import re
from handlers.applications import register_handlers as register_applications_handlers
from handlers.orders import register_handlers as register_orders_handlers
from handlers.stats import register_handlers as register_stats_handlers


# Создаем бота и диспетчер
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())
dp.middleware.setup(LoggingMiddleware())
# Регистрация всех обработчиков
register_applications_handlers(dp)
register_orders_handlers(dp)
register_stats_handlers(dp)
# Создаём экземпляр API клиента
api_client = APIClient()

# Инициализация базы данных
init_db()

# Шаги для авторизации
class AuthStates(StatesGroup):
    waiting_for_login = State()
    waiting_for_password = State()

# AIOHTTP сервер для обработки вебхуков
app = web.Application()

# Команда /start
@dp.message_handler(commands=['start'])
async def start_command(message: Message):
    """Приветственное сообщение при старте."""
    await message.answer(
        "Привет! Я бот для работы с вашим сайтом.\n"
        "Вот что я умею:\n"
        "- Получать статистику\n"
        "- Авторизоваться в системе\n"
        "- Работать с заказами\n"
        "- Отправлять уведомления о новых заявках\n"
        "\nВведите /menu, чтобы начать работу."
    )

# Команда menu
@dp.message_handler(commands=['menu'])
async def menu_command(message: Message):
    """Вызывает главное меню."""
    await render_main_menu(message, message.from_user.id)

# Основное меню
async def render_main_menu(message_or_call, user_id: int):
    """Отображает главное меню с учётом авторизации."""
    authorized = is_user_authorized(user_id)

    keyboard = InlineKeyboardMarkup()
    if authorized:
        keyboard.add(InlineKeyboardButton("📊 Статистика", callback_data="stats"))
        keyboard.add(InlineKeyboardButton("📦 Заказы", callback_data="orders"))
        keyboard.add(InlineKeyboardButton("📄 Заявки", callback_data="applications"))
        keyboard.add(InlineKeyboardButton("🏢 Поставщики", callback_data="suppliers"))
        keyboard.add(InlineKeyboardButton("🚪 Выход из системы", callback_data="logout"))
        keyboard.add(InlineKeyboardButton("ℹ️ Помощь", callback_data="help"))
        menu_message = "Вы авторизованы. Выберите действие:"
    else:
        keyboard.add(InlineKeyboardButton("🔑 Авторизация", callback_data="login"))
        keyboard.add(InlineKeyboardButton("ℹ️ Помощь", callback_data="help"))
        menu_message = "Вы не авторизованы. Пожалуйста, выполните авторизацию."

    if isinstance(message_or_call, CallbackQuery):
        await message_or_call.message.edit_text(menu_message, reply_markup=keyboard)
        await message_or_call.answer()
    elif isinstance(message_or_call, Message):
        await message_or_call.answer(menu_message, reply_markup=keyboard)



# Обработка команд с Inline-клавиатуры
@dp.callback_query_handler(lambda call: call.data in ["stats", "login", "logout", "help", "back_to_main_menu"])
async def handle_inline_commands(call: CallbackQuery):
    """Обработка команд с Inline-кнопок."""
    action = call.data

    if action == "stats":
        await show_stats_menu(call)
    elif action == "login":
        await login_command(call.message)
    elif action == "logout":
        await logout_command(call)
    elif action == "help":
        await help_command(call)
    elif action == "back_to_main_menu":
        # Возврат в главное меню
        await call.message.delete()
        await render_main_menu(call.message, call.from_user.id)

# Команда /help
async def help_command(call: CallbackQuery):
    """Отображает информацию о командах."""
    help_text = (
        "Доступные команды:\n"
        "- 📊 Статистика: просмотреть данные по диапазону\n"
        "- 🔑 Авторизация: войти в систему\n"
        "- 🚪 Выход из системы: разлогиниться\n"
        "- ℹ️ Помощь: показать это сообщение"
    )

    # Удаляем старое меню и отправляем статистику
    await call.message.delete()
    await call.message.answer(help_text)

    # Отображаем обновлённое меню
    await render_main_menu(call.message, call.from_user.id)
    

# Команда /login
async def login_command(message_or_call):
    """Начало авторизации."""
    if isinstance(message_or_call, Message):
        await message_or_call.answer("Введите ваш логин:")
    elif isinstance(message_or_call, CallbackQuery):
        await message_or_call.message.edit_text("Введите ваш логин:")
        await message_or_call.answer()
    await AuthStates.waiting_for_login.set()

# Обработка логина
@dp.message_handler(state=AuthStates.waiting_for_login)
async def process_login(message: Message, state: FSMContext):
    await state.update_data(login=message.text)
    await message.answer("Введите ваш пароль:")
    await AuthStates.waiting_for_password.set()

# Обработка пароля
@dp.message_handler(state=AuthStates.waiting_for_password)
async def process_password(message: Message, state: FSMContext):
    """Обработка пароля и завершение авторизации."""
    user_data = await state.get_data()
    login = user_data.get("login")
    password = message.text

    try:
        # Авторизация через API
        auth_response = api_client.login(login, password)
        if auth_response:
            access_token = auth_response.get("access_token")
            refresh_token = auth_response.get("refresh_token")
            
            # Сохраняем пользователя в базе данных
            add_user(
                telegram_id=message.from_user.id,
                access_token=access_token,
                refresh_token=refresh_token
            )
            await message.answer("Вы успешно авторизованы!")

            # Обновляем меню
            await render_main_menu(message, message.from_user.id)
        else:
            await message.answer("Неверный логин или пароль. Попробуйте снова.")
    except ValueError as e:
        await message.answer(f"Ошибка авторизации: {str(e)}")
    except Exception as e:
        await message.answer(f"Произошла ошибка: {str(e)}")
    finally:
        await state.finish()

# Команда /logout
async def logout_command(call: CallbackQuery):
    # message_or_call
    """Выход из системы."""
    user_id = call.from_user.id

    if is_user_authorized(user_id):
        remove_user(user_id)

        # Удаляем старое меню и отправляем сообщение
        await call.message.delete()
        await call.message.answer('Вы вышли из системы')

    else:
        # Удаляем старое меню и отправляем сообщение
        await call.message.delete()
        await call.message.answer('Вы не авторизованы')

    # Отображаем обновлённое меню
    await render_main_menu(call.message, call.from_user.id)


# Обработка кнопки “📦 Поставщики”
@dp.callback_query_handler(lambda call: call.data == "suppliers")
async def show_suppliers(call: CallbackQuery):
    """Отображает список поставщиков."""
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("4 точки", callback_data="supplier_tochki"))
    keyboard.add(InlineKeyboardButton("Бринекс", callback_data="supplier_brineks"))
    keyboard.add(InlineKeyboardButton("Медведь", callback_data="supplier_medved"))
    keyboard.add(InlineKeyboardButton("Шининвест", callback_data="supplier_shininvest"))
    keyboard.add(InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_main_menu"))
    await call.message.edit_text("Выберите поставщика:", reply_markup=keyboard)
    await call.answer()

@dp.callback_query_handler(lambda call: call.data.startswith("supplier_"))
async def show_supplier_menu(call: CallbackQuery):
    """Отображает меню конкретного поставщика."""
    supplier_slug = call.data.split("_")[-1]
    supplier_name = {
        "tochki": "4 точки",
        "brineks": "Бринекс",
        "medved": "Медведь",
        "shininvest": "Шининвест"
    }.get(supplier_slug, "Неизвестный поставщик")

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("📄 Информация об импорте", callback_data=f"import_{supplier_slug}"))
    keyboard.add(InlineKeyboardButton("⚙️ Настройка", callback_data=f"suppliersettings_{supplier_slug}"))
    keyboard.add(InlineKeyboardButton("🔙 Назад к поставщикам", callback_data="suppliers"))

    await call.message.edit_text(f"Меню поставщика: {supplier_name}", reply_markup=keyboard)
    await call.answer()

@dp.callback_query_handler(lambda call: call.data.startswith("import_"))
async def show_import_info(call: CallbackQuery):
    """Отображает информацию об импорте поставщика."""
    supplier_slug = call.data.split("_")[1]
    try:
        import_data = api_client.get_supplier_import(call.from_user.id, supplier_slug)
        if not import_data:
            await call.message.edit_text("Не удалось получить информацию об импорте. Попробуйте позже.")
            return

        supplier = import_data.get("supplier_data", {})
        tasks = import_data.get("task_results", {})
        tire_task = tasks.get("tire", {})
        disk_task = tasks.get("disk", {})

        import_text = (
            f"<b>🏢 Поставщик:</b> {supplier.get('name')}\n"
            f"<b>💰 Наценка:</b> {supplier.get('extra_charge')}\n\n"
            f"<b>Последние импорты:</b>\n"
            f"🔹 <b>Шины:</b> {tire_task.get('last_status', 'Нет данных')}\n"
            f"   <b>Дата:</b> {tire_task.get('last_run_time', 'Нет данных')}\n"
            f"🔹 <b>Диски:</b> {disk_task.get('last_status', 'Нет данных')}\n"
            f"   <b>Дата:</b> {disk_task.get('last_run_time', 'Нет данных')}\n"
        )

        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🔙 Назад к поставщику", callback_data=f"supplier_{supplier_slug}"))

        await call.message.edit_text(import_text, reply_markup=keyboard, parse_mode="HTML")
        await call.answer()
    except Exception as e:
        await call.message.edit_text(f"Произошла ошибка: {str(e)}")

# Добавление состояния для настройки поставщика
class SupplierSettingsStates(StatesGroup):
    waiting_for_extra_charge = State()

# Переход в раздел "Настройка"
@dp.callback_query_handler(lambda call: call.data.startswith("suppliersettings_"))
async def supplier_settings(call: CallbackQuery):
    """Отображает раздел настройки поставщика."""
    supplier_slug = call.data.split("_")[-1]
    
    # Новый текст сообщения с добавлением уникального элемента
    new_text = (
        f"Вы в разделе настройки поставщика: <b>{supplier_slug}</b>\n"
        f"🔧 Здесь вы можете настроить параметры для этого поставщика."
    )
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("✏️ Изменить наценку", callback_data=f"edit_extra_charge_{supplier_slug}"))
    keyboard.add(InlineKeyboardButton("🔙 Назад к поставщику", callback_data=f"supplier_{supplier_slug}"))
    
    # Проверяем, нужно ли обновлять сообщение
    if call.message.text != new_text or call.message.reply_markup != keyboard:
        await call.message.edit_text(new_text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await call.answer("Сообщение уже актуально.")  # Чтобы убрать "загрузка" в Telegram

# Начало изменения наценки
@dp.callback_query_handler(lambda call: call.data.startswith("edit_extra_charge_"))
async def edit_extra_charge_start(call: CallbackQuery):
    """Предлагает ввести новую наценку."""
    supplier_slug = call.data.split("_")[-1]
    await SupplierSettingsStates.waiting_for_extra_charge.set()
    # Сохраняем slug в состояние
    async with dp.current_state(user=call.from_user.id).proxy() as state_data:
        state_data["supplier_slug"] = supplier_slug
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("❌ Отменить", callback_data="cancel_edit"))
    await call.message.edit_text(
        f"Введите новую наценку для поставщика {supplier_slug}.\n"
        "Значение должно быть числом, не меньше 1. Например: 1.1 или 1,1.",
        reply_markup=keyboard
    )
    await call.answer()

# Обработка ввода наценки
@dp.message_handler(state=SupplierSettingsStates.waiting_for_extra_charge)
async def process_extra_charge_input(message: Message, state: FSMContext):
    """Обрабатывает ввод наценки."""
    extra_charge_input = message.text.strip()
    # Проверяем корректность значения
    if not re.match(r"^\d+(\.\d+|,\d+)?$", extra_charge_input) or float(extra_charge_input.replace(",", ".")) < 1:
        await message.answer("Некорректное значение. Убедитесь, что вы ввели число больше или равное 1. Например: 1.1 или 1,1.")
        return

    # Преобразуем значение к числовому формату
    extra_charge = float(extra_charge_input.replace(",", "."))
    
    # Получаем slug из состояния
    async with state.proxy() as state_data:
        supplier_slug = state_data["supplier_slug"]

    try:
        # Отправляем изменения через API
        response_data = api_client.update_supplier_settings(message.from_user.id, supplier_slug, extra_charge)

        # Проверяем ключ "status"
        if response_data.get("status") == "error":
            await message.answer(f"Не удалось обновить наценку. Ошибка: {response_data.get('message', 'Неизвестная ошибка')}")
        else:
            await message.answer(f"Наценка для поставщика {supplier_slug} успешно обновлена на {extra_charge}.")
    except Exception as e:
        await message.answer(f"Произошла ошибка: {str(e)}")
    finally:
        await state.finish()

    # Возвращаемся в настройки поставщика
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🔙 Назад к поставщику", callback_data=f"supplier_{supplier_slug}"))
    await message.answer(f"Настройки для поставщика {supplier_slug} обновлены.", reply_markup=keyboard)
    

# Отмена изменения наценки
@dp.callback_query_handler(lambda call: call.data == "cancel_edit", state=SupplierSettingsStates.waiting_for_extra_charge)
async def cancel_edit(call: CallbackQuery, state: FSMContext):
    """Отменяет изменение наценки."""
    await state.finish()
    await call.message.edit_text("Изменение наценки отменено.")
    await call.answer()
    # Отображаем обновлённое меню
    await render_main_menu(call.message, call.from_user.id)


# Вебхук для новых заказов
async def orders_webhook(request):
    """Обработка уведомлений о новых заказах."""
    try:
        order = await request.json()  # Получаем данные из запроса
        if not order:  # Проверяем, что данные существуют
            return web.json_response({"error": "Invalid data"}, status=400)

        # Основная информация о заказе
        detail = order['detail']
        order_text = (
            f"<b>📦 НОВЫЙ ЗАКАЗ №{detail['id']}</b>\n\n"
            f"<b>Информация о заказе:</b>\n"
            f"📝 <b>Статус:</b> {detail['status']['status_name']}\n"
            f"💰 <b>Сумма:</b> {detail['total_price_with_discount']} ₽\n"
            f"📦 <b>Количество товаров:</b> {sum(item['quantity'] for item in detail['items'])}\n"
            f"📦 <b>Количество позиций:</b> {len(detail['items'])}\n"
            f"📍 <b>Адрес доставки:</b> {detail['address'] or 'Не указан'}\n\n"
            f"<b>Информация о клиенте:</b>\n"
            f"👤 <b>Имя:</b> {detail['first_name']} {detail['last_name'] or ''} {detail['patronymic'] or ''}\n"
            f"📧 <b>Email:</b> {detail['email'] or 'Не указан'}\n"
            f"📞 <b>Телефон:</b> {detail['tel'] or 'Не указан'}\n\n"
        )

        # Добавление списка товаров
        order_text += "<b>🛒 Товары в заказе:</b>\n"
        for idx, item in enumerate(detail['items'], start=1):
            product = item['product']
            order_text += (
                f"{idx}. 🔹 <b>{product['name']}</b>\n"
                f"    🆔 Артикул: {product['item_number']}\n"
                f"    💰 Цена: {item['price']} ₽\n"
                f"    📦 Количество: {item['quantity']} шт.\n"
            )

            # Разбивка по поставщикам
            if 'product_supplier_info' in product and product['product_supplier_info']:
                order_text += "    📊 Остатки у поставщиков:\n"
                for supplier in product['product_supplier_info']:
                    supplier_info = supplier.get('supplier_info', {})
                    order_text += (
                        f"        🔸 <b>{supplier_info.get('name', 'Неизвестный поставщик')}:</b>\n"
                        f"           • Остаток: {supplier['quantity']} шт.\n"
                        f"           • Цена поставки: {supplier['purchase_price']} ₽\n"
                        f"           • Цена с наценкой: {supplier['extra_charge_price']} ₽\n"
                    )
            else:
                order_text += "    ❌ Нет данных о поставщиках.\n"

            order_text += "\n"

        # Формирование клавиатуры
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🔗 Перейти к заказу", url=f"https://ass74.ru/order/{detail['unique_token']}"))

        # Отправляем уведомления авторизованным пользователям
        authorized_users = get_authorized_users()
        async def send_notifications():
            for user_id in authorized_users:
                await bot.send_message(chat_id=user_id, text=order_text, reply_markup=keyboard, parse_mode="HTML")

        asyncio.create_task(send_notifications())
        return web.json_response({"status": "success"})

    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

# Вебхук для обратной связи
async def feedback_webhook(request):
    """Обработка уведомлений о новых заявках обратной связи."""
    try:
        application = await request.json()
        if not application:
            return web.json_response({"error": "Invalid data"}, status=400)

        # Формируем сообщение
        application_text = (
            f"<b>📄 НОВАЯ ЗАЯВКА №{application['id']}</b>\n\n"
            f"<b>Информация о заявке:</b>\n"
            f"📝 <b>Статус:</b> {application['status']}\n"
            f"📧 <b>Email:</b> {application['email'] or 'Не указан'}\n"
            f"📞 <b>Телефон:</b> {application['tel'] or 'Не указан'}\n"
            f"💬 <b>Комментарий:</b> {application['comment'] or 'Отсутствует'}\n"
            f"📅 <b>Создана:</b> {application['created']}\n"
        )

        # Отправляем уведомления авторизованным пользователям
        authorized_users = get_authorized_users()
        async def send_notifications():
            for user_id in authorized_users:
                await bot.send_message(chat_id=user_id, text=application_text, parse_mode="HTML")

        asyncio.create_task(send_notifications())
        return web.json_response({"status": "success"})

    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

# Добавление маршрутов вебхуков
app.router.add_post('/webhook/orders', orders_webhook)
app.router.add_post('/webhook/feedback', feedback_webhook)


# Основной запуск
if __name__ == "__main__":
    loop = asyncio.get_event_loop()

    # Запуск aiohttp-сервера
    runner = web.AppRunner(app)
    loop.run_until_complete(runner.setup())
    site = web.TCPSite(runner, "127.0.0.1", 5000)
    loop.run_until_complete(site.start())

    # Запуск Telegram-бота
    executor.start_polling(dp, skip_updates=True, loop=loop)