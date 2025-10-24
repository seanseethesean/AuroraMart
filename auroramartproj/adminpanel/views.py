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
            messages.success(request, "Product added")
            return redirect("adminpanel:product_list")
    else:
        form = ProductForm()
    return render(request, "adminpanel/product_edit.html", {"form": form, "title": "Add Product"})


@staff_member_required
def edit_product(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, "Product updated")
            return redirect("adminpanel:product_list")
    else:
        form = ProductForm(instance=product)
    return render(request, "adminpanel/product_edit.html", {"form": form, "title": "Edit Product", "product": product})


@staff_member_required
def delete_product(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == "POST":
        product.delete()
        messages.success(request, "Product deleted")
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
