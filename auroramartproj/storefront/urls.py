from django.urls import path
from . import views

app_name = 'storefront'

urlpatterns = [
    path('', views.home, name='home'),
    path('products/', views.product_list, name='product_list'),
    path('products/<int:pk>/', views.product_detail, name='product_detail'),
    path('cart/', views.cart_view, name='cart_view'),
    path('cart/add/<int:pk>/', views.cart_add, name='cart_add'),
    path('cart/remove/<int:pk>/', views.cart_remove, name='cart_remove'),
    path('cart/update/<int:pk>/', views.cart_update, name='cart_update'),
    path('checkout/', views.checkout, name='checkout'),
    path('order/placed/<int:order_id>/', views.order_placed, name='order_placed'),
    path('orders/', views.order_list, name='order_list'),
    path('orders/<int:pk>/confirm-delivery/', views.order_confirm_delivery, name='order_confirm_delivery'),
    path('profile/', views.profile, name='profile'),
    path('recommendations/', views.recommendations, name='recommendations'),
    path('login/',  views.StorefrontLoginView.as_view(), name='login'),
    path('logout/', views.StorefrontLogoutView.as_view(), name='logout'),
    path('register/', views.register, name='register'),
    path('onboarding/', views.onboarding, name='onboarding'),
]