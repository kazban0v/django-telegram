from django.contrib import admin
from django.utils.html import format_html
from main.models import Product, Category, Users

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

@admin.register(Users)
class UsersAdmin(admin.ModelAdmin):
    list_display = ('telegram_id', 'first_name', 'phone_number', 'email', 'created_at')  
    search_fields = ('telegram_id', 'first_name', 'email')  
    ordering = ('-created_at',)

