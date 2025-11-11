#!/usr/bin/env python3
import os, sys
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'auroramartproj.settings')
import django
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()
print('Users in DB:')
for u in User.objects.all():
    print('-', u.username, '| email=', u.email or '<no email>')
