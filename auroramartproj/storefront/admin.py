from django.contrib import admin

from .models import BasketHistory, Order, OrderItem


@admin.register(BasketHistory)
class BasketHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at', 'items_preview')
    search_fields = ('user__username', 'items')
    ordering = ('-created_at',)

    def items_preview(self, obj):
        return ', '.join(obj.items)[:80]

    items_preview.short_description = 'Items'


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'status', 'total_price', 'date_ordered', 'delivered_at')
    list_filter = ('status', 'date_ordered')
    search_fields = ('id', 'user__username')


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product', 'quantity', 'price')
    list_select_related = ('order', 'product')
