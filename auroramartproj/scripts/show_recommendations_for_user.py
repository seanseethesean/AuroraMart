#!/usr/bin/env python3
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'auroramartproj.settings')
import django
django.setup()

from django.test import RequestFactory
from django.contrib.auth import get_user_model
from storefront.views import recommendations

User = get_user_model()
user = User.objects.first()
if not user:
    print('No user found in database.')
    sys.exit(1)

rf = RequestFactory()
request = rf.get('/recommendations/')
# attach a session and user
request.user = user

# call view
response = recommendations(request)
print('Rendered response status:', getattr(response, 'status_code', None))
