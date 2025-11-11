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
    path('login/',  auth_views.LoginView.as_view(template_name='storefront/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='storefront:home'), name='logout'),
    path('register/', views.register, name='register'),
    path('onboarding/', views.onboarding, name='onboarding'),
    path('profile/', views.profile, name='profile'),
    # Password reset flows (uses Django's built-in auth views)
    path('password_reset/', auth_views.PasswordResetView.as_view(
        template_name='storefront/auth/password_reset.html',
        email_template_name='storefront/auth/password_reset_email.html',
        success_url=reverse_lazy('storefront:password_reset_done')
    ), name='password_reset'),

    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='storefront/auth/password_reset_done.html'
    ), name='password_reset_done'),

    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='storefront/auth/password_reset_confirm.html'
    ), name='password_reset_confirm'),

    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='storefront/auth/password_reset_complete.html'
    ), name='password_reset_complete'),
    # Password change (for logged-in users)
    path('password_change/', auth_views.PasswordChangeView.as_view(
        template_name='storefront/auth/password_change.html',
        success_url=reverse_lazy('storefront:password_change_done')
    ), name='password_change'),

    path('password_change/done/', auth_views.PasswordChangeDoneView.as_view(
        template_name='storefront/auth/password_change_done.html'
    ), name='password_change_done'),
]