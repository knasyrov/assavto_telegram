from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import Dispatcher
from api.client import APIClient

api_client = APIClient()


# Обработка кнопки “📦 Заказы”
async def show_orders(call: CallbackQuery):
    """Отображает список заказов (первая страница)."""
    await show_orders_page(call, 1)

# Обработка кнопки "Назад к заказам"
async def handle_orders_pagination(call: CallbackQuery):
    """Обрабатывает кнопки пагинации заказов."""
    page = int(call.data.split("_")[-1])  # Извлекаем номер страницы из callback_data
    await show_orders_page(call, page)  # Показываем указанную страницу

# Получение и отображение заказов
async def show_orders_page(call: CallbackQuery, page: int):
    """Отображает заказы для указанной страницы."""
    try:
        # Запрос к API
        orders_response = api_client.get_orders(call.from_user.id, page)
        orders = orders_response.get("data", [])
        total_pages = orders_response.get("total_pages", 1)
        current_page = orders_response.get("current_page", 1)

        if not orders:
            await call.message.edit_text("Заказы не найдены.")
            await render_main_menu(call, call.from_user.id)
            return

        # Формируем кнопки для заказов
        keyboard = InlineKeyboardMarkup()
        for order in orders:
            button_text = f"№{order['id']} | {order['status']['status_name']} | {order['total_price_with_discount']} ₽"
            keyboard.add(InlineKeyboardButton(button_text, callback_data=f"order_{order['id']}"))

        # Добавляем кнопки пагинации
        if current_page > 1:
            keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data=f"orders_page_{current_page - 1}"))
        if current_page < total_pages:
            keyboard.add(InlineKeyboardButton("➡️ Вперёд", callback_data=f"orders_page_{current_page + 1}"))
        keyboard.add(InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_main_menu"))

        # Обновляем сообщение
        await call.message.edit_text(f"📦 Заказы (страница {current_page} из {total_pages}):", reply_markup=keyboard)
        await call.answer()
    except Exception as e:
        await call.message.edit_text(f"Произошла ошибка: {str(e)}")
        await render_main_menu(call, call.from_user.id)        



# Просмотр информации о заказе
async def show_order_details(call: CallbackQuery):
    """Отображает детали выбранного заказа с товарами."""
    order_id = int(call.data.split("_")[1])
    try:
        # Получение информации о заказе
        order = api_client.get_order_details(call.from_user.id, order_id)
        if not order:
            await call.message.edit_text("Информация о заказе не найдена.")
            return

        # Основная информация о заказе
        detail = order['detail']
        order_text = (
            f"<b>📦 Заказ №{detail['id']}</b>\n\n"
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
        keyboard.add(InlineKeyboardButton("🔙 Назад к заказам", callback_data=f"orders_page_1"))

        # Отправка информации
        await call.message.edit_text(order_text, reply_markup=keyboard, parse_mode="HTML")
        await call.answer()
    except Exception as e:
        await call.message.edit_text(f"Произошла ошибка: {str(e)}")


def register_handlers(dp: Dispatcher):
    """Регистрирует обработчики заказов."""
    dp.register_callback_query_handler(show_orders, lambda call: call.data == "orders")
    dp.register_callback_query_handler(handle_orders_pagination, lambda call: call.data.startswith("orders_page_"))
    dp.register_callback_query_handler(show_order_details, lambda call: call.data.startswith("order_"))