from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import user_passes_test, login_required
from django.contrib import messages
from django.contrib.auth.models import User
from adminpanel.models import Product
from storefront.models import Order
from .forms import ProductForm
from django.contrib.auth.models import User

# --- Helper for restricting access ---
def staff_required(user):
    return user.is_staff

# --- Login view ---
def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, "Invalid email or password")
            return redirect('adminpanel:login')

        user = authenticate(request, username=user.username, password=password)
        if user is not None and user.is_staff:
            login(request, user)
            return redirect('adminpanel:dashboard')
        else:
            messages.error(request, "Access denied.")
    return render(request, 'adminpanel/login.html')

# --- Dashboard ---
@user_passes_test(staff_required)
def dashboard(request):
    product_count = Product.objects.count()
    customer_count = User.objects.filter(is_staff=False).count()
    total_inventory = sum(p.stock for p in Product.objects.all())
    return render(request, 'adminpanel/dashboard.html', {
        'product_count': product_count,
        'customer_count': customer_count,
        'total_inventory': total_inventory,
    })

# --- Products ---
@user_passes_test(staff_required)
def product_list(request):
    products = Product.objects.all()
    return render(request, 'adminpanel/product_list.html', {'products': products})

@user_passes_test(staff_required)
def add_product(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('adminpanel:product_list')
    else:
        form = ProductForm()
    return render(request, 'adminpanel/product_edit.html', {'form': form})

@user_passes_test(staff_required)
def edit_product(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            return redirect('adminpanel:product_list')
    else:
        form = ProductForm(instance=product)
    return render(request, 'adminpanel/product_edit.html', {'form': form})

@user_passes_test(staff_required)
def delete_product(request, pk):
    product = get_object_or_404(Product, pk=pk)
    product.delete()
    return redirect('adminpanel:product_list')

# --- Customers ---
@user_passes_test(staff_required)
def customer_list(request):
    customers = User.objects.filter(role='customer')
    return render(request, 'adminpanel/customer_list.html', {'customers': customers})

@user_passes_test(staff_required)
def customer_detail(request, pk):
    customer = get_object_or_404(User, pk=pk)
    return render(request, 'adminpanel/customer_detail.html', {'customer': customer})
