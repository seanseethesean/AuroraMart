from django.db import models
from django.contrib.auth.models import User
from django.core.files.storage import FileSystemStorage
from django.conf import settings
import os

class Product(models.Model):
    sku = models.CharField(max_length=50, unique=True, null=True, blank=True, help_text="Unique product identifier")
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    description = models.TextField(blank=True)
    _admin_images_location = os.path.join(settings.BASE_DIR, 'adminpanel', 'static', 'adminpanel', 'images')
    admin_images_fs = FileSystemStorage(location=_admin_images_location, base_url='/static/adminpanel/images/')
    image = models.ImageField(upload_to='', storage=admin_images_fs, blank=True, null=True)
    # Product label and optional discount
    LABEL_CHOICES = [
        ('', 'None'),
        ('new', 'New Arrival'),
        ('discounted', 'Discounted'),
        ('last_pieces', 'Last Pieces'),
    ]
    label = models.CharField(max_length=32, choices=LABEL_CHOICES, blank=True, default='')
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True,
                                           help_text='Percent discount e.g. 10 for 10%')

    def get_display_price(self):
        """Return price after applying discount_percent if present."""
        if self.discount_percent:
            try:
                dp = float(self.discount_percent)
                discounted = float(self.price) * (1 - dp / 100.0)
                return round(discounted, 2)
            except Exception:
                return self.price
        return self.price

    def __str__(self):
        return self.name

class Customer(models.Model):
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other')
    ]
    
    EMPLOYMENT_CHOICES = [
        ('FT', 'Full-time'),
        ('PT', 'Part-time'),
        ('SE', 'Self-employed'),
        ('ST', 'Student')
    ]
    
    EDUCATION_CHOICES = [
        ('HS', 'High School'),
        ('DP', 'Diploma'),
        ('BD', 'Bachelor'),
        ('MS', 'Master'),
        ('DR', 'Doctorate')
    ]
    
    INCOME_RANGES = [
        ('0-2000', '$0 - $2,000'),
        ('2001-4000', '$2,001 - $4,000'),
        ('4001-6000', '$4,001 - $6,000'),
        ('6001-8000', '$6,001 - $8,000'),
        ('8001-10000', '$8,001 - $10,000'),
        ('10001+', 'Above $10,000')
    ]
    
    CATEGORIES = [
        ('electronics', 'Electronics'),
        ('hair', 'Hair & Beauty'),
        ('fashion', 'Fashion'),
        ('sports', 'Sports & Outdoors'),
        ('home', 'Home & Kitchen'),
        ('books', 'Books'),
        ('groceries', 'Groceries & Gourmet')
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    age = models.IntegerField(null=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, null=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    
    # Required onboarding fields
    preferred_categories = models.CharField(max_length=100, help_text="Comma-separated list of 3 preferred categories", null=True, blank=True)
    
    # Optional onboarding fields
    employment_status = models.CharField(max_length=2, choices=EMPLOYMENT_CHOICES, blank=True, null=True)
    occupation = models.CharField(max_length=100, blank=True)
    education = models.CharField(max_length=2, choices=EDUCATION_CHOICES, blank=True, null=True)
    household_size = models.PositiveIntegerField(blank=True, null=True)
    has_children = models.BooleanField(blank=True, null=True)
    monthly_income = models.CharField(max_length=10, choices=INCOME_RANGES, blank=True, null=True)
    
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
