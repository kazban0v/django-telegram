from django.contrib import admin
from django.utils.html import format_html
from main.models import (
    Product, Category, Users, Order, OrderItem,
    SubCategory, DeliveryMethod, Cart, UserProfile, AdminNotification
)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'stock', 'category', 'is_popular', 'created_at', 'image_tag')
    list_filter = ('category', 'is_popular', 'created_at')
    search_fields = ('name', 'description')
    list_editable = ('is_popular', 'stock')
    ordering = ('-created_at',)

    def image_tag(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="50" height="50" />'.format(obj.image.url))
        return "-"
    image_tag.short_description = "Image"

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

@admin.register(SubCategory)
class SubCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'description')
    list_filter = ('parent',)
    search_fields = ('name', 'parent__name')

@admin.register(Users)
class UsersAdmin(admin.ModelAdmin):
    list_display = ('telegram_id', 'first_name', 'phone_number', 'email', 'created_at')  
    search_fields = ('telegram_id', 'first_name', 'email')  
    ordering = ('-created_at',)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'address', 'city', 'postal_code', 'preferred_delivery_method')
    list_filter = ('city', 'preferred_delivery_method')
    search_fields = ('user__first_name', 'address', 'city')

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'status', 'total_price', 'created_at')
    list_filter = ('status',)
    search_fields = ('user__first_name', 'id')

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if obj and obj.status == 'completed':
            form.base_fields['status'].choices = [
                ('completed', 'Завершен'),
                ('cancelled', 'Отменен')
            ]
        return form

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product', 'quantity', 'price')

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'quantity', 'total_price')
    list_filter = ('user', 'product')
    search_fields = ('user__first_name', 'product__name')

    def total_price(self, obj):
        return obj.total_price()
    total_price.short_description = "Total Price"

@admin.register(DeliveryMethod)
class DeliveryMethodAdmin(admin.ModelAdmin):
    list_display = ('name', 'base_price', 'price_per_km', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)

@admin.register(AdminNotification)
class AdminNotificationAdmin(admin.ModelAdmin):
    list_display = ('type', 'message', 'created_at', 'is_read')
    list_filter = ('type', 'is_read')
    search_fields = ('message',)
    ordering = ('-created_at',)
