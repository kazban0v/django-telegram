from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from main.models import Order
from telebot import TeleBot

bot = TeleBot('7937515092:AAF2FhDyBOG_g4KqsrehJzENOB9joTbPhbg') 

@receiver(post_save, sender=Order)
def notify_admins_on_new_order(sender, instance, created, **kwargs):
    if created:
        message = (
            f"🔔 Новый заказ #{instance.id}\n"
            f"👤 Пользователь: {instance.user.first_name} (ID: {instance.user.telegram_id})\n"
            f"💰 Сумма: {instance.total_price}₸\n"
            f"📅 Дата: {instance.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            f"🏷️ Статус: {instance.get_status_display()}"
        )
        admin_ids = getattr(settings, 'TELEGRAM_ADMIN_IDS', [])
        for admin_id in admin_ids:
            bot.send_message(admin_id, message)
