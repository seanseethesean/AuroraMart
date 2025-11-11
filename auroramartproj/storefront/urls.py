from django.urls import path, reverse_lazy
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
    path('cart/update/<int:pk>/', views.cart_update, name='cart_update'),
    path('checkout/', views.checkout, name='checkout'),
    path('order/placed/<int:order_id>/', views.order_placed, name='order_placed'),
    path('orders/', views.order_list, name='order_list'),
    path('orders/<int:pk>/confirm-delivery/', views.order_confirm_delivery, name='order_confirm_delivery'),
    path('recommendations/', views.recommendations, name='recommendations'),
    path('login/',  views.StorefrontLoginView.as_view(template_name='storefront/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='storefront:home'), name='logout'),
    path('register/', views.register, name='register'),
    path('onboarding/', views.onboarding, name='onboarding'),
    path('profile/', views.profile, name='profile'),
    # Password reset flows removed per project request.
    # Password change (for logged-in users)
    path('password_change/', auth_views.PasswordChangeView.as_view(
        template_name='storefront/auth/password_change.html',
        success_url=reverse_lazy('storefront:password_change_done')
    ), name='password_change'),

    path('password_change/done/', auth_views.PasswordChangeDoneView.as_view(
        template_name='storefront/auth/password_change_done.html'
    ), name='password_change_done'),
    # Stripe payment intent endpoint used by checkout.js
    path('create-payment-intent/', views.create_payment_intent, name='create_payment_intent'),
]