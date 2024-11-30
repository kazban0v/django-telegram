import os
import django
from telebot import types
import telebot

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from main.models import Product, Category, Users, Cart

TOKEN = '7937515092:AAF2FhDyBOG_g4KqsrehJzENOB9joTbPhbg'
bot = telebot.TeleBot(TOKEN)

user_states = {}

def get_main_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("🛒 Категории"), 
                 types.KeyboardButton("🔍 Поиск"))
    keyboard.add(types.KeyboardButton("📦 Список товаров"))
    keyboard.add(types.KeyboardButton("🗂 Корзина"))
    return keyboard

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

@bot.message_handler(func=lambda message: message.text == "🛒 Категории")
def show_companies(message):
    companies = Category.objects.all()
    if companies.exists():
        markup = types.InlineKeyboardMarkup()
        for company in companies:
            markup.add(types.InlineKeyboardButton(company.name, callback_data=f"company_{company.id}"))
        bot.send_message(message.chat.id, "Выберите категорию:", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "Категории пока отсутствуют.", reply_markup=get_main_keyboard())

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
            
            bot.answer_callback_query(call.id, "Товар удален из корзины.")
            view_cart(call.message)  
        else:
            bot.answer_callback_query(call.id, "Товар не найден в корзине.")
    
    except ValueError:
        bot.answer_callback_query(call.id, "Ошибка: неверные данные!")

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
