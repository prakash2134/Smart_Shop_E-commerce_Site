from django.conf import settings
from django.db import models
U = settings.AUTH_USER_MODEL

class Product(models.Model):
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=60, default="General")
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Price in INR")
    stock = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to="products/", blank=True)
    sold = models.PositiveIntegerField(default=0)
    class Meta: db_table = "shop_product"
    def __str__(self): return self.name

class CartItem(models.Model):
    user = models.ForeignKey(U, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    class Meta: db_table = "shop_cartitem"

class Order(models.Model):
    user = models.ForeignKey(U, on_delete=models.CASCADE)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    payment_status = models.CharField(max_length=20, default="pending")
    order_status = models.CharField(max_length=20, default="pending",
        choices=[(s, s.title()) for s in ("pending", "processing", "shipped", "delivered", "cancelled")])
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: db_table = "shop_order"
    def __str__(self): return f"Order #{self.pk}"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    class Meta: db_table = "shop_orderitem"

class Payment(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=30, default="stripe")
    transaction_id = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: db_table = "shop_payment"

class Notification(models.Model):
    user = models.ForeignKey(U, on_delete=models.CASCADE)
    type = models.CharField(max_length=30)
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: db_table = "shop_notification"
