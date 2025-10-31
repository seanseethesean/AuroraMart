from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

app_name = 'storefront'

urlpatterns = [
    path('', views.home, name='home'),
    path('products/', views.product_list, name='product_list'),
    path('products/<int:pk>/', views.product_detail, name='product_detail'),
    path('cart/', views.cart_view, name='cart_view'),
    path('cart/add/<int:pk>/', views.cart_add, name='cart_add'),
    path('cart/remove/<int:pk>/', views.cart_remove, name='cart_remove'),
    path('checkout/', views.checkout, name='checkout'),
    path('order/placed/<int:order_id>/', views.order_placed, name='order_placed'),
    path('recommendations/', views.recommendations, name='recommendations'),
    path('login/',  auth_views.LoginView.as_view(template_name='storefront/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='storefront:home'), name='logout'),
    path('register/', views.register, name='register'),
]