from django import forms
from .models import Product, PRODUCT_CATEGORY_CHOICES


LEGACY_CATEGORY_MAP = {
    'home & kitchen': 'home',
    'home and kitchen': 'home',
    'sports & outdoors': 'sports',
    'sports and outdoors': 'sports',
    'beauty': 'hair',
    'beauty & personal care': 'hair',
    'beauty and personal care': 'hair',
    'hair & beauty': 'hair',
    'hair and beauty': 'hair',
    'groceries': 'groceries',
    'groceries & gourmet': 'groceries',
    'groceries and gourmet': 'groceries',
    'books': 'books',
    'electronics': 'electronics',
    'fashion': 'fashion',
    'others': 'others',
}


class ProductForm(forms.ModelForm):
    category = forms.ChoiceField(choices=PRODUCT_CATEGORY_CHOICES, widget=forms.Select(attrs={'class': 'form-control'}))

    class Meta:
        model = Product
        fields = ['name', 'category', 'price', 'stock', 'image', 'description', 'label', 'discount_percent']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'stock': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'label': forms.Select(attrs={'class': 'form-control'}),
            'discount_percent': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get('instance') or self.instance
        if instance and instance.category:
            normalized = self._normalize_category(instance.category)
            if normalized in dict(PRODUCT_CATEGORY_CHOICES):
                self.initial.setdefault('category', normalized)
            else:
                # legacy value not in choices – keep it selectable once to avoid data loss
                self.fields['category'].choices = list(PRODUCT_CATEGORY_CHOICES) + [(instance.category, instance.category)]
                self.initial.setdefault('category', instance.category)

    def _normalize_category(self, value: str) -> str:
        if not value:
            return value
        key = value.lower().strip()
        return LEGACY_CATEGORY_MAP.get(key, value)

    def clean_category(self):
        category = self.cleaned_data.get('category')
        normalized = self._normalize_category(category)
        if normalized in dict(PRODUCT_CATEGORY_CHOICES):
            return normalized
        return category
