import os
import django
from telebot import types
import telebot

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from main.models import Product, Category, Users, Cart, SubCategory, Order, OrderItem, UserProfile
from django.db.models import Sum
from django.db import transaction
import logging

logger = logging.getLogger(__name__)

TOKEN = '7937515092:AAF2FhDyBOG_g4KqsrehJzENOB9joTbPhbg'
bot = telebot.TeleBot(TOKEN)

user_states = {}

def get_main_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(
        types.KeyboardButton("🛒 Категории"), 
        types.KeyboardButton("🔍 Поиск")
    )
    keyboard.add(
        types.KeyboardButton("📦 Список товаров"),
        types.KeyboardButton("🗂 Корзина")
    )
    keyboard.add(
        types.KeyboardButton("📋 Мои заказы"),
        types.KeyboardButton("👤 Личный кабинет")    
    )
    return keyboard


def create_order_from_cart(user):
    cart_items = Cart.objects.filter(user=user)
    if not cart_items.exists():
        return None
    try:
        with transaction.atomic():
            total_price = sum(item.total_price() for item in cart_items)
            order = Order.objects.create(
                user=user,
                total_price=total_price,
                status='pending'
            )
            for cart_item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    product=cart_item.product,
                    quantity=cart_item.quantity,
                    price=cart_item.product.price
                )
                product = cart_item.product
                product.stock -= cart_item.quantity
                product.save()
            cart_items.delete()
            return order
    except Exception as e:
        logger.error(f"Ошибка создания заказа: {e}")
        return None

@bot.message_handler(func=lambda message: message.text == "📋 Мои заказы")
def view_order_history(message):
    telegram_id = message.from_user.id
    user = Users.objects.filter(telegram_id=telegram_id).first()
    if not user:
        bot.send_message(message.chat.id, "Ошибка: пользователь не найден.")
        return
    orders = Order.objects.filter(user=user).order_by('-created_at')
    if orders.exists():
        for order in orders:
            order_items = "\n".join([
                f"{item.product.name} - {item.quantity} шт. ({item.price}₸)" 
                for item in order.items.all()
            ])
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton(
                    "📦 Статус заказа", 
                    callback_data=f"order_status_{order.id}"
                )
            )
            bot.send_message(
                message.chat.id,
                f"📝 Заказ #{order.id}\n"
                f"📅 Дата: {order.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                f"💰 Сумма: {order.total_price}₸\n"
                f"🏷️ Статус: {order.get_status_display()}\n\n"
                f"🛍️ Товары:\n{order_items}",
                reply_markup=markup
            )
    else:
        bot.send_message(message.chat.id, "У вас пока нет заказов.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("order_status_"))
def check_order_status(call):
    try:
        order_id = int(call.data.split("_")[-1])
        order = Order.objects.get(id=order_id)
        status_details = {
            'pending': "Ожидает оплаты. Пожалуйста, завершите оплату.",
            'paid': "Оплата получена. Заказ готовится к обработке.",
            'processing': "Заказ обрабатывается. Скоро будет отправлен.",
            'shipped': "Заказ отправлен. Ожидайте доставку.",
            'completed': "Заказ успешно доставлен.",
            'cancelled': "Заказ отменен."
        }
        bot.answer_callback_query(
            call.id, 
            status_details.get(order.status, "Неизвестный статус"),
            show_alert=True
        )
    except Order.DoesNotExist:
        bot.answer_callback_query(call.id, "Заказ не найден.")


@bot.message_handler(commands=['start'])
def send_privet(message):
    telegram_id = message.from_user.id
    first_name = message.from_user.first_name
    user, created = Users.objects.get_or_create(
        telegram_id=telegram_id,
        defaults={'first_name': first_name}
    )
    if created:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        button_phone = types.KeyboardButton("📱 Отправить номер телефона", request_contact=True)
        markup.add(button_phone)
        bot.send_message(
            message.chat.id,
            f"Привет, {first_name}! Добро пожаловать в BKStore. Для завершения регистрации отправьте ваш номер телефона.",
            reply_markup=markup
        )
        user_states[telegram_id] = "wait_phone"
    else:
        bot.send_message(
            message.chat.id,
            f"С возвращением {first_name} в BKStore. Выберите действие из меню:",
            reply_markup=get_main_keyboard()
        )

@bot.message_handler(content_types=['contact'])
def handle_contact(message):
    if message.contact is not None:
        telegram_id = message.from_user.id
        phone_number = message.contact.phone_number
        user = Users.objects.filter(telegram_id=telegram_id).first()
        if user:
            user.phone_number = phone_number
            user.save()
            bot.reply_to(message, "Спасибо! Ваш номер телефона успешно сохранён. Теперь отправьте ваш email.")
            user_states[telegram_id] = "wait_email"
        else:
            bot.reply_to(message, "Ошибка: пользователь не найден. Попробуйте снова.")

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "wait_email")
def handle_email(message):
    telegram_id = message.from_user.id
    email = message.text
    user = Users.objects.filter(telegram_id=telegram_id).first()
    if user:
        user.email = email
        user.save()
        bot.reply_to(message, "Спасибо! Ваш email успешно сохранён. Теперь отправьте ваше имя.")
        user_states[telegram_id] = "wait_name"
    else:
        bot.reply_to(message, "Ошибка: пользователь не найден. Попробуйте снова.")

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "wait_name")
def handle_name(message):
    telegram_id = message.from_user.id
    first_name = message.text
    user = Users.objects.filter(telegram_id=telegram_id).first()
    if user:
        user.first_name = first_name
        user.save()
        bot.reply_to(message, "Регистрация завершена! Теперь вы можете пользоваться BKStore. Выберите действие:",
                     reply_markup=get_main_keyboard())
        user_states.pop(telegram_id, None)
    else:
        bot.reply_to(message, "Ошибка: пользователь не найден. Попробуйте снова.")

@bot.message_handler(func=lambda message: message.text == "👤 Личный кабинет")
def personal_cabinet(message):
    telegram_id = message.from_user.id
    user = Users.objects.filter(telegram_id=telegram_id).first()
    if not user:
        bot.send_message(message.chat.id, "Ошибка: пользователь не найден.")
        return
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✏️ Редактировать профиль", callback_data="edit_profile"),
        types.InlineKeyboardButton("📍 Адрес доставки", callback_data="edit_address")
    )
    bot.send_message(
        message.chat.id,
        f"👤 Личный кабинет\n"
        f"Имя: {user.first_name}\n"
        f"Телефон: {user.phone_number}\n"
        f"Email: {user.email}",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "edit_profile")
def edit_profile(call):
    telegram_id = call.from_user.id
    user_states[telegram_id] = "edit_profile"
    bot.send_message(call.message.chat.id, "Введите новое имя:")

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "edit_profile")
def update_profile_name(message):
    telegram_id = message.from_user.id
    user = Users.objects.filter(telegram_id=telegram_id).first()
    if user:
        user.first_name = message.text
        user.save()
        bot.send_message(message.chat.id, "Имя обновлено!", reply_markup=get_main_keyboard())
        user_states.pop(telegram_id)
    else:
        bot.send_message(message.chat.id, "Ошибка: пользователь не найден.")

@bot.callback_query_handler(func=lambda call: call.data == "edit_address")
def edit_address(call):
    telegram_id = call.from_user.id
    user_states[telegram_id] = "edit_address"
    bot.send_message(call.message.chat.id, "Введите новый адрес доставки:")

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "edit_address")
def update_address(message):
    telegram_id = message.from_user.id
    user = Users.objects.filter(telegram_id=telegram_id).first()
    if user:
        profile, created = UserProfile.objects.get_or_create(user=user)
        profile.address = message.text
        profile.save()
        bot.send_message(message.chat.id, "Адрес доставки обновлен!", reply_markup=get_main_keyboard())
    else:
        bot.send_message(message.chat.id, "Ошибка: пользователь не найден.")


@bot.message_handler(func=lambda message: message.text == "🛒 Категории")
def show_categories(message):
    categories = Category.objects.all()  
    if categories.exists():
        markup = types.InlineKeyboardMarkup()
        for category in categories:
            markup.add(types.InlineKeyboardButton(category.name, callback_data=f"category_{category.id}"))
        bot.send_message(message.chat.id, "Выберите бренд:", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "Категории пока отсутствуют.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("category_"))
def show_subcategories(call):
    category_id = int(call.data.split("_")[1])  
    subcategories = SubCategory.objects.filter(parent_id=category_id)  
    if subcategories.exists():
        markup = types.InlineKeyboardMarkup()
        for subcategory in subcategories:
            markup.add(types.InlineKeyboardButton(subcategory.name, callback_data=f"subcategory_{subcategory.id}"))
        bot.edit_message_text("Выберите подкатегорию:", chat_id=call.message.chat.id, message_id=call.message.id, reply_markup=markup)
    else:
        bot.edit_message_text("Подкатегории для этого бренда пока отсутствуют.", chat_id=call.message.chat.id, message_id=call.message.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("subcategory_"))
def show_products(call):
    subcategory_id = int(call.data.split("_")[1])  
    products = Product.objects.filter(category_id=subcategory_id)  
    if products.exists():
        for product in products:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("Добавить в корзину 🛒", callback_data=f"add_to_cart_{product.id}"))
            bot.send_message(
                call.message.chat.id,
                f"📱 {product.name}\n💵 Цена: {product.price}₸\n📦 В наличии: {product.stock} шт.\nОписание: {product.description}",
                reply_markup=markup
            )
    else:
        bot.edit_message_text("Товары для этой подкатегории пока отсутствуют.", chat_id=call.message.chat.id, message_id=call.message.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("company_"))
def show_products(call):
    company_id = int(call.data.split("_")[1])
    company = Category.objects.get(id=company_id)
    products = Product.objects.filter(category=company)
    if products.exists():
        for product in products:
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("Добавить в корзину 🛒", callback_data=f"add_to_cart_{product.id}")
            )
            markup.add(
                types.InlineKeyboardButton("⬅️ Назад к категории", callback_data="back_to_companies")
            )
            bot.send_message(
                call.message.chat.id,
                f"📱 {product.name}\n"
                f"💵 Цена: {product.price}₸\n"
                f"📦 В наличии: {product.stock} шт.\n"
                f"Описание: {product.description}",
                reply_markup=markup
            )
    else:
        bot.send_message(call.message.chat.id, f"В категории {company.name} пока нет товаров.",
                         reply_markup=get_main_keyboard())

@bot.callback_query_handler(func=lambda call: call.data.startswith("add_to_cart_"))
def add_to_cart(call):
    try:
        product_id = int(call.data.replace("add_to_cart_", ""))  
    except ValueError:
        bot.answer_callback_query(call.id, "Ошибка: неверные данные!")
        return
    telegram_id = call.from_user.id
    user = Users.objects.filter(telegram_id=telegram_id).first()
    if not user:
        bot.answer_callback_query(call.id, "Ошибка: пользователь не найден.")
        return
    product = Product.objects.filter(id=product_id).first()
    if not product:
        bot.answer_callback_query(call.id, "Ошибка: товар не найден.")
        return
    cart_item, created = Cart.objects.get_or_create(user=user, product=product, defaults={'quantity': 1})
    if not created:
        cart_item.quantity += 1
        cart_item.save()
    bot.answer_callback_query(call.id, f"Товар '{product.name}' добавлен в корзину!")

@bot.message_handler(func=lambda message: message.text == "🗂 Корзина")
def view_cart(message):
    telegram_id = message.from_user.id
    user = Users.objects.filter(telegram_id=telegram_id).first()
    
    if not user:
        bot.send_message(message.chat.id, "Ошибка: пользователь не найден.")
        return
    
    cart_items = Cart.objects.filter(user=user)
    if cart_items.exists():
        markup = types.InlineKeyboardMarkup()
        for item in cart_items:
            item_markup = types.InlineKeyboardMarkup()
            item_markup.add(
                types.InlineKeyboardButton("➖ Убрать", callback_data=f"remove_from_cart_{item.product.id}"),
                types.InlineKeyboardButton("➕ Добавить", callback_data=f"add_to_cart_{item.product.id}")
            )
            
            bot.send_message(
                message.chat.id,
                f"{item.product.name} - {item.quantity} шт. (Итого: {item.total_price()}₸)",
                reply_markup=item_markup
            )
        
        total_price = sum(item.total_price() for item in cart_items)
        checkout_markup = types.InlineKeyboardMarkup()
        checkout_markup.add(types.InlineKeyboardButton("Оформить заказ 💳", callback_data="checkout"))
        
        bot.send_message(
            message.chat.id,
            f"Итого к оплате: {total_price}₸",
            reply_markup=checkout_markup
        )
    else:
        bot.send_message(message.chat.id, "Ваша корзина пуста.", reply_markup=get_main_keyboard())

@bot.callback_query_handler(func=lambda call: call.data.startswith("remove_from_cart_"))
def remove_from_cart(call):
    try:
        product_id = int(call.data.replace("remove_from_cart_", ""))
        telegram_id = call.from_user.id
        user = Users.objects.filter(telegram_id=telegram_id).first()
        if not user:
            bot.answer_callback_query(call.id, "Ошибка: пользователь не найден.")
            return
        cart_item = Cart.objects.filter(user=user, product_id=product_id).first()
        if cart_item:
            if cart_item.quantity > 1:
                cart_item.quantity -= 1
                cart_item.save()
            else:
                cart_item.delete()
            bot.answer_callback_query(call.id, "Товар успешно удален из корзины.")
        else:
            bot.answer_callback_query(call.id, "Товар не найден в корзине.")
        view_cart(call.message)
    except ValueError:
        bot.answer_callback_query(call.id, "Ошибка: неверные данные!")
    except Exception as e:
        logger.error(f"Ошибка при удалении из корзины: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")

def calculate(delivery_method, distance):
    base_price = delivery_method.base_price
    price_per_km = delivery_method.price_per_km
    total_delivery_price = base_price + (distance * price_per_km)
    return total_delivery_price

@bot.callback_query_handler(func=lambda call: call.data == "checkout")
def start_checkout(call):
    telegram_id = call.from_user.id
    user = Users.objects.filter(telegram_id=telegram_id).first()
    if not user:
        bot.answer_callback_query(call.id, "Ошибка: пользователь не найден.") 
        return
    cart_items = Cart.objects.filter(user=user)
    if not cart_items.exists():
        bot.answer_callback_query(call.id, "Ваша корзина пуста.")
        return
    for item in cart_items:
        if item.quantity > item.product.stock:
            bot.answer_callback_query(call.id, f"Недостаточно товара {item.product.name} на складе.")
            return
    total_price = sum(item.total_price() for item in cart_items)
    payment_markup = types.InlineKeyboardMarkup()
    payment_markup.add(
        types.InlineKeyboardButton(
            "Оплатить через CryptoBot 💳", 
            url="t.me/send?start=IV2NwI3gdQpG"
        )
    )
    bot.send_message(
        call.message.chat.id, 
        f"Сумма к оплате: {total_price}₸\n"
        "Нажмите кнопку ниже для перехода к оплате, до того как оплатите напишите ваше имя и номер телефона для связи:",
        reply_markup=payment_markup
    )

def create_admin_panel(bot):
    @bot.message_handler(commands=['admin'])
    def admin_menu(message):
        if not is_admin(message.from_user.id):
            bot.reply_to(message, "У вас нет доступа.")
            return
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(
            "📦 Управление товарами",
            "📋 Статистика заказов",
            "🚚 Настройка доставки"
        )
        bot.send_message(message.chat.id, "Административная панель:", reply_markup=markup)

    @bot.message_handler(func=lambda message: message.text == "📦 Управление товарами")
    def manage_products(message):
        if not is_admin(message.from_user.id):
            bot.reply_to(message, "У вас нет доступа.")
            return
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("➕ Добавить товар", callback_data="add_product"),
            types.InlineKeyboardButton("✏️ Изменить товар", callback_data="edit_product")
        )
        bot.send_message(message.chat.id, "Управление товарами:", reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data == "add_product")
    def add_product(call):
        bot.send_message(call.message.chat.id, "Добавление товара пока не реализовано. Напишите название товара.")

    @bot.callback_query_handler(func=lambda call: call.data == "edit_product")
    def edit_product(call):
        bot.send_message(call.message.chat.id, "Изменение товара пока не реализовано. Напишите ID товара.")

    @bot.message_handler(func=lambda message: message.text == "📋 Статистика заказов")
    def view_order_statistics(message):
        if not is_admin(message.from_user.id):
            bot.reply_to(message, "У вас нет доступа.")
            return
        stats = order_statistics()
        bot.send_message(message.chat.id, stats)

    @bot.message_handler(func=lambda message: message.text == "🚚 Настройка доставки")
    def manage_delivery_settings(message):
        if not is_admin(message.from_user.id):
            bot.reply_to(message, "У вас нет доступа.")
            return
        bot.send_message(message.chat.id, "Настройка доставки пока не реализована. Напишите ваш запрос.")

def is_admin(telegram_id):
    admin_ids = [855861024]  
    return telegram_id in admin_ids

def order_statistics():
    total_orders = Order.objects.count()
    total_revenue = Order.objects.aggregate(total=Sum('total_price'))['total']
    top_products = OrderItem.objects.values('product__name').annotate(total_quantity=Sum('quantity')).order_by('-total_quantity')[:5]
    report = f"📊 Статистика продаж:\n" \
             f"Всего заказов: {total_orders}\n" \
             f"Общая выручка: {total_revenue}₸\n" \
             "Топ-5 продаваемых товаров:\n"
    for product in top_products:
        report += f"- {product['product__name']}: {product['total_quantity']} шт.\n"
    return report
create_admin_panel(bot)

@bot.message_handler(func=lambda message: message.text == "🔍 Поиск")
def search_product_prompt(message):
    bot.send_message(
        message.chat.id,
        "Введите название товара для поиска:",
        reply_markup=get_main_keyboard()
    )
    user_states[message.from_user.id] = "searching"

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "searching")
def search_product(message):
    query = message.text
    products = Product.objects.filter(name__icontains=query)
    if products.exists():
        product_list = "\n".join([f"{product.name} - {product.price}₸ (В наличии: {product.stock} шт.)" for product in products])
        bot.send_message(message.chat.id, f"Найдено:\n{product_list}", reply_markup=get_main_keyboard())
    else:
        bot.send_message(message.chat.id, f"Товары, соответствующие запросу '{query}', не найдены.",
                         reply_markup=get_main_keyboard())

@bot.message_handler(func=lambda message: message.text == "📦 Список товаров")
def list_product(message):
    products = Product.objects.all()
    if products.exists():
        response = "\n".join([f"{p.name} - {p.price}₸ (В наличии: {p.stock} шт.)" for p in products])
    else:
        response = "Товары на данный момент отсутствуют, мы сообщим вам, когда поступят!"
    bot.reply_to(message, response)

bot.polling()
