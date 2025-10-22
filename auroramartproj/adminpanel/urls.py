from django.urls import path
from . import views

app_name = 'adminpanel'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('products/add/', views.product_add, name='product_add'),
    path('products/<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('products/<int:pk>/delete/', views.product_delete, name='product_delete'),
]
