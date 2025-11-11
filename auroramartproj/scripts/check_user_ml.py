#!/usr/bin/env python3
import os, sys
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'auroramartproj.settings')
import django
django.setup()
from django.contrib.auth import get_user_model
from adminpanel.ml_utils import predict_preferred_category_for_customer, load_models
User = get_user_model()
user = User.objects.first()
if not user:
    print('No users')
    sys.exit(1)
print('User:', user.username, 'id=', user.id)
customer = getattr(user, 'customer', None)
print('Has customer profile?', bool(customer))
if customer:
    print('preferred_categories:', getattr(customer, 'preferred_categories', None))

models = load_models()
print('Models loaded:', {k: (v is not None) for k,v in models.items()})
try:
    pred = predict_preferred_category_for_customer(customer)
    print('predict_preferred_category_for_customer ->', repr(pred))
except Exception as e:
    print('Prediction raised:', e)
