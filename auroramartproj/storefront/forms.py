from django import forms
from adminpanel.models import Customer

class OnboardingForm(forms.ModelForm):
    preferred_categories = forms.MultipleChoiceField(
        choices=Customer.CATEGORIES,
        widget=forms.CheckboxSelectMultiple,
        help_text="Select exactly 3 categories"
    )

    class Meta:
        model = Customer
        fields = [
            'age', 'gender', 'preferred_categories',  # Required fields
            'employment_status', 'occupation', 'education',  # Optional fields
            'household_size', 'has_children', 'monthly_income'
        ]
        widgets = {
            'age': forms.NumberInput(attrs={'class': 'form-control'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'employment_status': forms.Select(attrs={'class': 'form-control'}),
            'occupation': forms.TextInput(attrs={'class': 'form-control'}),
            'education': forms.Select(attrs={'class': 'form-control'}),
            'household_size': forms.NumberInput(attrs={'class': 'form-control'}),
            'has_children': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'monthly_income': forms.Select(attrs={'class': 'form-control'})
        }

    def clean_preferred_categories(self):
        categories = self.cleaned_data.get('preferred_categories')
        if categories and len(categories) != 3:
            raise forms.ValidationError("Please select exactly 3 categories.")
        return ','.join(categories)  # Store as comma-separated string