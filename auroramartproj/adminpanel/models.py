from django.db import models
from django.contrib.auth.models import User

class Product(models.Model):
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='products/', blank=True, null=True)

    def __str__(self):
        return self.name



class Customer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    age = models.IntegerField(blank=True, null=True)
    gender = models.CharField(max_length=20, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    income = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    join_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.username


class RecommendationRule(models.Model):
    antecedent = models.CharField(max_length=200)  # e.g. "A + B"
    consequent = models.CharField(max_length=200)  # e.g. "→ C"
    confidence = models.FloatField(default=0.0)
    support = models.FloatField(default=0.0)

    def __str__(self):
        return f"{self.antecedent} → {self.consequent}"
