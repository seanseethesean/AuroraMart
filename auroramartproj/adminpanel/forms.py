from django import forms
from .models import Product

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['sku', 'name', 'category', 'description', 'price', 'stock', 'image']
