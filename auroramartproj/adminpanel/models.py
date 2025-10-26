from django.db import models
from django.contrib.auth.models import User
from django.core.files.storage import FileSystemStorage
from django.conf import settings
import os

class Product(models.Model):
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    description = models.TextField(blank=True)
    # Store uploaded product images inside the adminpanel static folder so
    # they are available under /static/adminpanel/images/
    _admin_images_location = os.path.join(settings.BASE_DIR, 'adminpanel', 'static', 'adminpanel', 'images')
    admin_images_fs = FileSystemStorage(location=_admin_images_location, base_url='/static/adminpanel/images/')
    image = models.ImageField(upload_to='', storage=admin_images_fs, blank=True, null=True)

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
