from django.db import models
from django.core.validators import MinValueValidator
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from telebot import TeleBot

class Users(models.Model):
    telegram_id = models.BigIntegerField(unique=True)
    first_name = models.CharField(max_length=100, blank=True, null=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.first_name} ({self.telegram_id})"

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

class SubCategory(models.Model):
    parent = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='subcategories')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.parent.name})"

class DeliveryMethod(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_per_km = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class Product(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    stock = models.PositiveIntegerField(default=0)
    is_popular = models.BooleanField(default=False)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    category = models.ForeignKey(SubCategory, on_delete=models.CASCADE, related_name='products')
    min_stock_threshold = models.PositiveIntegerField(default=10)

    def __str__(self):
        return f"{self.name} ({self.category.name}) ({self.stock} шт.)"
    
    def check_stock_level(self):
        if self.stock <= self.min_stock_threshold:
            create_admin_notification(
                'low_stock', 
                f'Низкий остаток товара: {self.name} - осталось {self.stock} шт.'
            )

class UserProfile(models.Model):
    user = models.OneToOneField(Users, on_delete=models.CASCADE, related_name='profile')
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    postal_code = models.CharField(max_length=20, blank=True, null=True)
    preferred_delivery_method = models.ForeignKey(
        DeliveryMethod, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )

    def __str__(self):
        return f"Профиль {self.user.first_name}"

class Cart(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='cart_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='cart_items')
    quantity = models.PositiveIntegerField(default=1)
    def total_price(self):
        return self.product.price * self.quantity
    def __str__(self):
        return f"{self.user.first_name} - {self.product.name} x {self.quantity}"

class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Ожидает оплаты'),
        ('paid', 'Оплачен'),
        ('processing', 'В обработке'),
        ('shipped', 'Отправлен'),
        ('completed', 'Завершен'),
        ('cancelled', 'Отменен'),
    ]
    user = models.ForeignKey(Users, on_delete=models.CASCADE)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    delivery_method = models.ForeignKey(
        DeliveryMethod, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    delivery_address = models.TextField(blank=True, null=True)
    delivery_distance = models.FloatField(null=True, blank=True)
    delivery_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    delivery_comment = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Заказ #{self.id} - {self.user.first_name}"
    
    def calculate_delivery_price(self):
        if not self.delivery_method or not self.delivery_distance:
            return 0
        base_price = self.delivery_method.base_price
        price_per_km = self.delivery_method.price_per_km
        total_delivery_price = base_price + (self.delivery_distance * price_per_km)
        return round(total_delivery_price, 2)
    def save(self, *args, **kwargs):
        if self.delivery_method and self.delivery_distance:
            self.delivery_price = self.calculate_delivery_price()
        super().save(*args, **kwargs)

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def total_price(self):
        return self.price * self.quantity

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"

class AdminNotification(models.Model):
    NOTIFICATION_TYPES = [
        ('new_order', 'Новый заказ'),
        ('low_stock', 'Низкий остаток товара'),
        ('user_registration', 'Новая регистрация'),
    ]

    type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.get_type_display()} - {self.created_at}"

def create_admin_notification(notification_type, message):
    AdminNotification.objects.create(
        type=notification_type,
        message=message
    )

bot = TeleBot('7937515092:AAF2FhDyBOG_g4KqsrehJzENOB9joTbPhbg')

@receiver(post_save, sender=Order)  
def notify(sender, instance, created, **kwargs):
    if created:
        message = (
            f"🔔 Новый заказ #{instance.id}\n"
            f"👤 Пользователь: {instance.user.first_name} (ID: {instance.user.telegram_id})\n"
            f"💰 Сумма: {instance.total_price}₸\n"
            f"📅 Дата: {instance.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            f"🏷️ Статус: {dict(Order.STATUS_CHOICES).get(instance.status, 'Неизвестный')}"
        )
        admin_ids = getattr(settings, 'TELEGRAM_ADMIN_IDS', [])
        if not admin_ids:
            print("Администраторские Telegram ID не настроены в settings.py")
            return
        for admin_id in admin_ids:
            try:
                bot.send_message(admin_id, message)
            except Exception as e:
                print(f"Ошибка при отправке сообщения администратору {admin_id}: {e}")

@receiver(post_save, sender=Users)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=Users)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()