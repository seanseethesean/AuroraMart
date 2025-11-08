from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.urls import reverse
from django.db.models import Sum

from .models import Product, Customer
from .forms import ProductForm
from storefront.models import Order
from django.contrib.auth.models import User
from storefront.models import OrderItem
from django import forms

staff_required = staff_member_required(login_url='adminpanel:login')


# Simple forms for customer create/edit and password reset
class CustomerForm(forms.Form):
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    password = forms.CharField(required=False)
    phone = forms.CharField(required=False)
    address = forms.CharField(required=False)
    age = forms.IntegerField(required=False)
    gender = forms.CharField(required=False)
    income = forms.DecimalField(required=False, max_digits=10, decimal_places=2)


class PasswordResetForm(forms.Form):
    password = forms.CharField()


def login_view(request):
    """Login using email + password. Only staff users allowed into adminpanel views."""
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            user = None

        if user is not None:
            user = authenticate(request, username=user.username, password=password)
            if user is not None:
                if user.is_staff:
                    login(request, user)
                    return redirect("adminpanel:dashboard")
                else:
                    messages.error(request, "You do not have permission to access the admin panel.")
            else:
                messages.error(request, "Invalid credentials")
        else:
            messages.error(request, "Invalid credentials")

    return render(request, "adminpanel/login.html")


def logout_view(request):
    logout(request)
    return redirect(reverse("adminpanel:login"))


@staff_required
def dashboard(request):
    product_count = Product.objects.count()
    customer_count = Customer.objects.count()
    total_inventory = Product.objects.aggregate(total_stock=Sum("stock"))['total_stock'] or 0
    recent_orders = Order.objects.all().order_by('-date_ordered')[:5]  # Get 5 most recent orders

    context = {
        "product_count": product_count,
        "customer_count": customer_count,
        "total_inventory": total_inventory,
        "recent_orders": recent_orders,
    }
    return render(request, "adminpanel/dashboard.html", context)


@staff_required
def product_list(request):
    products = Product.objects.all()
    return render(request, "adminpanel/product/product_list.html", {"products": products})


@staff_required
def add_product(request):
    """Add new product. Staff-only."""
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Product added successfully!")
            return redirect("adminpanel:product_list")
    else:
        form = ProductForm()
    return render(request, "adminpanel/product/product_edit.html", {
        "form": form,
        "title": "Add Product",
        "show_messages": True
    })


@staff_required
def edit_product(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, "Product updated successfully")
            return redirect("adminpanel:product_list")
    else:
        form = ProductForm(instance=product)
    return render(request, "adminpanel/product/product_edit.html", {
        "form": form, 
        "title": "Edit Product",
        "product": product,
        "show_messages": False  # Don't show messages on form page
    })


@staff_required
def delete_product(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == "POST":
        name = product.name  # Store name before deletion
        product.delete()
        messages.success(request, f"Product '{name}' deleted successfully")
        return redirect("adminpanel:product_list")
    return render(request, "adminpanel/product/product_confirm_delete.html", {"product": product})


@staff_required
def customer_list(request):
    customers = Customer.objects.select_related("user").all()
    return render(request, "adminpanel/customer/customer_list.html", {"customers": customers})


@staff_required
def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    return render(request, "adminpanel/customer/customer_detail.html", {"customer": customer})


@staff_required
def toggle_customer(request, pk):
    if request.method != "POST":
        return redirect("adminpanel:customer_list")
        
    customer = get_object_or_404(Customer, pk=pk)
    customer.user.is_active = not customer.user.is_active
    customer.user.save()
    
    action = "activated" if customer.user.is_active else "deactivated"
    messages.success(request, f"Customer account {action} successfully.")
    
    # Redirect back to the page that made the request
    redirect_to = request.META.get('HTTP_REFERER')
    if redirect_to and redirect_to.endswith(str(pk)):
        return redirect("adminpanel:customer_detail", pk=pk)
    return redirect("adminpanel:customer_list")


@staff_required
def order_list(request):
    # Allow filtering by customer id and product id via GET params
    customer_id = request.GET.get('customer')
    product_id = request.GET.get('product')
    orders = Order.objects.all().select_related('user')
    if customer_id:
        orders = orders.filter(user__id=customer_id)
    if product_id:
        orders = orders.filter(items__product__id=product_id).distinct()
    return render(request, 'adminpanel/order/order_list.html', {'orders': orders, 'customer_id': customer_id, 'product_id': product_id})


@staff_required
def order_detail(request, pk):
    order = get_object_or_404(Order, pk=pk)
    items = order.items.select_related('product')
    return render(request, 'adminpanel/order/order_detail.html', {'order': order, 'items': items})


@staff_required
def customer_create(request):
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            user = User.objects.create_user(username=data['username'], email=data['email'], password=data.get('password') or None)
            Customer.objects.create(user=user, phone=data.get('phone',''), address=data.get('address',''), age=data.get('age'), gender=data.get('gender',''), income=data.get('income'))
            messages.success(request, 'Customer created')
            return redirect('adminpanel:customer_list')
    else:
        form = CustomerForm()
    return render(request, 'adminpanel/customer/customer_form.html', {'form': form, 'title': 'Create Customer'})


@staff_required
def customer_edit(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            user = customer.user
            user.username = data['username']
            user.email = data['email']
            if data.get('password'):
                user.set_password(data['password'])
            user.save()
            customer.phone = data.get('phone','')
            customer.address = data.get('address','')
            customer.age = data.get('age')
            customer.gender = data.get('gender','')
            customer.income = data.get('income')
            customer.save()
            messages.success(request, 'Customer updated')
            return redirect('adminpanel:customer_detail', pk=customer.pk)
    else:
        form = CustomerForm(initial={
            'username': customer.user.username,
            'email': customer.user.email,
            'phone': customer.phone,
            'address': customer.address,
            'age': customer.age,
            'gender': customer.gender,
            'income': customer.income,
        })
    return render(request, 'adminpanel/customer/customer_form.html', {'form': form, 'title': 'Edit Customer', 'customer': customer})


@staff_required
def customer_delete(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        username = customer.user.username
        customer.user.delete()
        messages.success(request, f'Customer {username} deleted')
        return redirect('adminpanel:customer_list')
    return render(request, 'adminpanel/customer/customer_confirm_delete.html', {'customer': customer})


@staff_required
def customer_reset_password(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            password = form.cleaned_data['password']
            customer.user.set_password(password)
            customer.user.save()
            messages.success(request, 'Password reset successfully')
            return redirect('adminpanel:customer_detail', pk=pk)
    else:
        form = PasswordResetForm()
    return render(request, 'adminpanel/customer/customer_reset_password.html', {'form': form, 'customer': customer})


@staff_required
def customer_orders(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    orders = Order.objects.filter(user=customer.user).order_by('-date_ordered')
    return render(request, 'adminpanel/customer/customer_orders.html', {'customer': customer, 'orders': orders})
