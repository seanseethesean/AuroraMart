from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.urls import reverse
from django.db.models import Sum

from .models import Product, Customer
from .forms import ProductForm


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


@staff_member_required
def dashboard(request):
    product_count = Product.objects.count()
    customer_count = Customer.objects.count()
    total_inventory = Product.objects.aggregate(total_stock=Sum("stock"))['total_stock'] or 0

    context = {
        "product_count": product_count,
        "customer_count": customer_count,
        "total_inventory": total_inventory,
    }
    return render(request, "adminpanel/dashboard.html", context)


@staff_member_required
def product_list(request):
    products = Product.objects.all()
    return render(request, "adminpanel/product_list.html", {"products": products})


@staff_member_required
def add_product(request):
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Product added successfully")
            return redirect("adminpanel:product_list")
    else:
        form = ProductForm()
    return render(request, "adminpanel/product_edit.html", {
        "form": form, 
        "title": "Add Product",
        "show_messages": False  # Don't show messages on form page
    })


@staff_member_required
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
    return render(request, "adminpanel/product_edit.html", {
        "form": form, 
        "title": "Edit Product",
        "product": product,
        "show_messages": False  # Don't show messages on form page
    })


@staff_member_required
def delete_product(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == "POST":
        name = product.name  # Store name before deletion
        product.delete()
        messages.success(request, f"Product '{name}' deleted successfully")
        return redirect("adminpanel:product_list")
    return render(request, "adminpanel/product_confirm_delete.html", {"product": product})


@staff_member_required
def customer_list(request):
    customers = Customer.objects.select_related("user").all()
    return render(request, "adminpanel/customer_list.html", {"customers": customers})


@staff_member_required
def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    return render(request, "adminpanel/customer_detail.html", {"customer": customer})


@staff_member_required
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
