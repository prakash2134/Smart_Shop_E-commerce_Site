from django.contrib import admin
from django.core.mail import send_mail
from .models import *

admin.site.site_header = "Smartshop Admin"

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "stock", "sold")
    list_editable = ("price", "stock")
    list_filter = ("category",)
    search_fields = ("name",)

class ItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "total", "payment_status", "order_status", "created_at")
    list_editable = ("order_status",)
    list_filter = ("order_status", "payment_status")
    inlines = [ItemInline]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if change and "order_status" in form.changed_data:
            msg = f"Order #{obj.pk} is now {obj.order_status}."
            Notification.objects.create(user=obj.user, type="shipping", message=msg)
            if obj.user.email:
                send_mail("Order update", msg, None, [obj.user.email], fail_silently=True)

admin.site.register([Payment, Notification, CartItem])
