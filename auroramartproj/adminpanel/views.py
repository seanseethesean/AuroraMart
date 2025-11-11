from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
import logging
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

        # Be tolerant of duplicate User rows with the same email. In some
        # datasets (or from import mistakes) multiple users may share an
        # email address which would make User.objects.get(...) raise
        # MultipleObjectsReturned. Prefer the oldest user (by id) in that
        # case and log a warning so admins can clean up the duplicates.
        user = None
        if email:
            qs = User.objects.filter(email__iexact=email).order_by('id')
            if qs.count() > 1:
                logging.getLogger(__name__).warning("Multiple User objects found for email=%s; using the first by id=%s", email, qs.first().id)
            user = qs.first()

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
    # Add simple search/filter support via ?q= querystring. Search matches SKU, name, category, or description.
    q = (request.GET.get('q') or '').strip()
    products_qs = Product.objects.all().order_by('id')
    if q:
        from django.db.models import Q
        products_qs = products_qs.filter(
            Q(name__icontains=q) | Q(sku__icontains=q) | Q(category__icontains=q) | Q(description__icontains=q)
        )
    products = list(products_qs)
    return render(request, "adminpanel/product/product_list.html", {"products": products, 'q': q})


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
    """List orders with optional filtering by customer id and product SKU."""
    orders_qs = (
        Order.objects
        .all()
        .select_related('user', 'user__customer')
        .prefetch_related('items__product')
        .order_by('-date_ordered')
    )

    customer_id = (request.GET.get('customer') or '').strip()
    product_sku = (request.GET.get('product') or '').strip()

    orders = orders_qs
    if customer_id:
        if customer_id.isdigit():
            customer_pk = int(customer_id)
            orders = orders.filter(user__customer__id=customer_pk)
        else:
            messages.error(request, "Customer ID must be a positive whole number.")

    if product_sku:
        orders = orders.filter(items__product__sku__iexact=product_sku).distinct()

    orders = list(orders)
    for order in orders:
        try:
            order.customer_profile = order.user.customer
        except Customer.DoesNotExist:
            order.customer_profile = None
        # Expose the raw status so templates can show specific labels
        order.display_status = getattr(order, 'status', None) or ''

    context = {
        'orders': orders,
        'customer_id': customer_id,
        'product_sku': product_sku,
    }
    return render(request, 'adminpanel/order/order_list.html', context)


@staff_required
def order_detail(request, pk):
    order = get_object_or_404(Order, pk=pk)
    items = order.items.select_related('product')

    # Handle status update POST from the admin UI
    if request.method == 'POST':
        new_status = (request.POST.get('status') or '').strip()
        valid_statuses = [s[0] for s in Order.STATUS_CHOICES]
        if new_status and new_status in valid_statuses:
            # Admins are allowed to set Processing/Shipped/Out for Delivery.
            # Delivered must be confirmed by the customer, so disallow admins from setting it here.
            if new_status == Order.STATUS_DELIVERED:
                messages.error(request, 'Delivered status must be set by the customer. Admins cannot mark an order as Delivered.')
            else:
                # Clear delivered_at when moving away from delivered
                order.status = new_status
                order.delivered_at = None
                order.save(update_fields=['status', 'delivered_at'])
                messages.success(request, f"Order status updated to '{new_status}'.")
                return redirect('adminpanel:order_detail', pk=order.pk)
        else:
            messages.error(request, 'Invalid status selected.')

    # Admin-facing status label
    if getattr(order, 'status', None) == Order.STATUS_DELIVERED:
        display_status = 'Completed'
    else:
        display_status = 'In Progress'

    # Admins may change Processing / Shipped / Out for Delivery, but Delivered should be set by the customer.
    # Provide a reduced set for the edit form (exclude Delivered) so admins can't mark orders as Delivered.
    status_choices_for_form = [s for s in Order.STATUS_CHOICES if s[0] != Order.STATUS_DELIVERED]
    return render(request, 'adminpanel/order/order_detail.html', {
        'order': order,
        'items': items,
        'display_status': display_status,
        'status_choices': status_choices_for_form,
    })


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
