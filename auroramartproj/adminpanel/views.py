from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import user_passes_test
from .models import Product, Customer, RecommendationRule
from .forms import ProductForm  # create this form shortly

def staff_required(user):
    return user.is_staff

@user_passes_test(staff_required)
def dashboard(request):
    products = Product.objects.all()
    customers = Customer.objects.all()
    rules = RecommendationRule.objects.all()
    return render(request, 'adminpanel/dashboard.html', {
        'products': products,
        'customers': customers,
        'rules': rules
    })

@user_passes_test(staff_required)
def product_add(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('adminpanel:dashboard')
    else:
        form = ProductForm()
    return render(request, 'adminpanel/product_form.html', {'form': form})

@user_passes_test(staff_required)
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            return redirect('adminpanel:dashboard')
    else:
        form = ProductForm(instance=product)
    return render(request, 'adminpanel/product_form.html', {'form': form, 'product': product})

@user_passes_test(staff_required)
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    product.delete()
    return redirect('adminpanel:dashboard')
