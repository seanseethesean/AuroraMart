from django.db import models
from accounts.models import UserProfile

class Customer(models.Model):
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
    ]

    user_profile = models.OneToOneField(UserProfile, on_delete=models.CASCADE)
    age = models.PositiveIntegerField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    employment = models.CharField(max_length=100, blank=True)
    income_range = models.CharField(max_length=100, blank=True)
    preferred_category = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return self.user_profile.user.username
