from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from adminpanel.models import Customer


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    first_name = forms.CharField(required=True, max_length=150, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(required=True, max_length=150, widget=forms.TextInput(attrs={'class': 'form-control'}))

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
        return user

class OnboardingForm(forms.ModelForm):
    preferred_categories = forms.MultipleChoiceField(
        choices=Customer.CATEGORIES,
        widget=forms.CheckboxSelectMultiple,
        help_text="Select up to 3 categories"
    )

    class Meta:
        model = Customer
        fields = [
            'age', 'gender', 'preferred_categories',  # Required fields
            'employment_status', 'occupation', 'education',  # Optional fields
            'household_size', 'has_children', 'monthly_income'
        ]
        widgets = {
            'age': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'employment_status': forms.Select(attrs={'class': 'form-control'}),
            'occupation': forms.TextInput(attrs={'class': 'form-control'}),
            'education': forms.Select(attrs={'class': 'form-control'}),
            'household_size': forms.NumberInput(attrs={'class': 'form-control'}),
            'has_children': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'monthly_income': forms.Select(attrs={'class': 'form-control'})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        customer = self.instance
        if customer and customer.preferred_categories:
            self.initial['preferred_categories'] = [c.strip() for c in customer.preferred_categories.split(',') if c]

    def clean_preferred_categories(self):
        categories = self.cleaned_data.get('preferred_categories')
        if not categories:
            raise forms.ValidationError("Please select at least one category.")
        if len(categories) > 3:
            raise forms.ValidationError("Select no more than 3 categories.")
        return ','.join(categories)  # Store as comma-separated string

    def clean_age(self):
        """Ensure age is a reasonable non-negative integer."""
        age = self.cleaned_data.get('age')
        if age in (None, ''):
            return age
        try:
            age_int = int(age)
        except (ValueError, TypeError):
            raise forms.ValidationError("Please enter a valid age.")
        if age_int < 0:
            raise forms.ValidationError("Age cannot be negative.")
        if age_int > 120:
            raise forms.ValidationError("Please enter a realistic age.")
        return age_int


class ProfileUpdateForm(forms.ModelForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    first_name = forms.CharField(required=True, max_length=150, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(required=True, max_length=150, widget=forms.TextInput(attrs={'class': 'form-control'}))
    preferred_categories = forms.MultipleChoiceField(
        choices=Customer.CATEGORIES,
        widget=forms.CheckboxSelectMultiple,
        help_text="Select up to 3 categories"
    )

    class Meta:
        model = Customer
        fields = [
            'phone', 'address', 'age', 'gender', 'preferred_categories',
            'employment_status', 'occupation', 'education',
            'household_size', 'has_children', 'monthly_income'
        ]
        widgets = {
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'age': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'employment_status': forms.Select(attrs={'class': 'form-control'}),
            'occupation': forms.TextInput(attrs={'class': 'form-control'}),
            'education': forms.Select(attrs={'class': 'form-control'}),
            'household_size': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'has_children': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'monthly_income': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        customer = self.instance
        if customer and customer.preferred_categories:
            self.initial['preferred_categories'] = [c.strip() for c in customer.preferred_categories.split(',') if c]
        if customer and customer.user:
            self.initial.setdefault('email', customer.user.email)
            self.initial.setdefault('first_name', customer.user.first_name)
            self.initial.setdefault('last_name', customer.user.last_name)

    def clean_preferred_categories(self):
        categories = self.cleaned_data.get('preferred_categories')
        if not categories:
            raise forms.ValidationError("Please select at least one category.")
        if len(categories) > 3:
            raise forms.ValidationError("Select no more than 3 categories.")
        return ','.join(categories)

    def clean_age(self):
        age = self.cleaned_data.get('age')
        if age in (None, ''):
            return age
        try:
            age_int = int(age)
        except (ValueError, TypeError):
            raise forms.ValidationError("Please enter a valid age.")
        if age_int < 0:
            raise forms.ValidationError("Age cannot be negative.")
        if age_int > 120:
            raise forms.ValidationError("Please enter a realistic age.")
        return age_int

    def save(self, commit=True):
        customer = super().save(commit=False)
        user = customer.user
        user.email = self.cleaned_data.get('email', user.email)
        user.first_name = self.cleaned_data.get('first_name', user.first_name)
        user.last_name = self.cleaned_data.get('last_name', user.last_name)
        if commit:
            user.save()
            customer.save()
        return customer