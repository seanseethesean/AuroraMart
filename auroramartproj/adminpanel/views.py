from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import user_passes_test
from products.models import Product
from .forms import ProductForm

# Only staff can access adminpanel
staff_required = user_passes_test(lambda u: u.is_active and u.is_staff)

@staff_required
def dashboard(request):
    """Admin dashboard landing page"""
    return render(request, "adminpanel/dashboard.html")


@staff_required
def product_list(request):
    """List all products"""
    products = Product.objects.all().order_by("name")
    return render(request, "adminpanel/product_list.html", {"products": products})


@staff_required
def product_create(request):
    """Create a new product"""
    if request.method == "POST":
        form = ProductForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("adminpanel:product_list")
    else:
        form = ProductForm()
    return render(request, "adminpanel/product_form.html", {"form": form, "mode": "Create"})


@staff_required
def product_edit(request, pk):
    """Edit an existing product"""
    product = get_object_or_404(Product, pk=pk)
    if request.method == "POST":
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            return redirect("adminpanel:product_list")
    else:
        form = ProductForm(instance=product)
    return render(request, "adminpanel/product_form.html", {"form": form, "mode": "Edit"})
