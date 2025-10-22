from django.db import models
from django.contrib.auth.models import User
from adminpanel.models import Product

class CartItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')

    def subtotal(self):
        return self.quantity * self.product.price

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"


class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    address = models.TextField()
    payment_method = models.CharField(max_length=50, default='Card')
    status = models.CharField(max_length=50, default='Processing')
    date_ordered = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order #{self.id} - {self.user.username}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product.name} ({self.quantity})"


class Recommendation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    reason = models.CharField(max_length=255, blank=True, null=True)  # e.g. “Because you bought X”
    generated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Recommendation for {self.user.username}: {self.product.name}"
