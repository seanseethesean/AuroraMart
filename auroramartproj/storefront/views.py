from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum
from adminpanel.models import Product
from .models import CartItem, Order, OrderItem, Recommendation
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login as auth_login
from adminpanel.models import Customer

# -----------------------------
# Log In
# -----------------------------
def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # ensure a Customer profile exists
            Customer.objects.get_or_create(user=user)
            auth_login(request, user)
            return redirect('storefront:home')
    else:
        form = UserCreationForm()
    return render(request, 'storefront/register.html', {'form': form})

# -----------------------------
# HOME PAGE
# -----------------------------
def home(request):
    products = Product.objects.all()[:8]  # show 8 featured items
    return render(request, 'storefront/home.html', {'products': products})

# -----------------------------
# PRODUCT LIST
# -----------------------------
from django.db.models import Q

def product_list(request):
    qs = Product.objects.all().order_by('name')

    q = request.GET.get('q') or ""
    cat = request.GET.get('cat') or ""

    if q:
        qs = qs.filter(
            Q(name__icontains=q) | Q(description__icontains=q) | Q(sku__icontains=q)
        )
    if cat:
        qs = qs.filter(category__iexact=cat)

    categories = Product.objects.values_list('category', flat=True).distinct().order_by('category')
    return render(request, 'storefront/product_list.html', {
        'products': qs,
        'categories': categories,
    })

# -----------------------------
# PRODUCT DETAIL
# -----------------------------
def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    return render(request, 'storefront/product_detail.html', {'product': product})

# -----------------------------
# CART VIEW
# -----------------------------
@login_required
def cart_view(request):
    cart_items = CartItem.objects.filter(user=request.user)
    total_price = sum(item.subtotal() for item in cart_items)
    return render(request, 'storefront/cart.html', {
        'cart_items': cart_items,
        'total_price': total_price,
        'total': total_price,
    })


@login_required
def cart_update(request, pk):
    """Update quantity for a cart item. Supports set, increment, decrement actions."""
    if request.method != 'POST':
        return redirect('storefront:cart_view')

    action = request.POST.get('action')
    quantity = request.POST.get('quantity')
    cart_item = get_object_or_404(CartItem, user=request.user, product__pk=pk)

    if action == 'increment':
        cart_item.quantity += 1
    elif action == 'decrement':
        if cart_item.quantity > 1:
            cart_item.quantity -= 1
    elif quantity is not None:
        try:
            q = int(quantity)
            if q > 0:
                cart_item.quantity = q
        except ValueError:
            pass

    cart_item.save()
    return redirect('storefront:cart_view')

# -----------------------------
# ADD TO CART
# -----------------------------
@login_required
def cart_add(request, pk):
    product = get_object_or_404(Product, pk=pk)
    quantity = int(request.POST.get('quantity', 1))
    cart_item, created = CartItem.objects.get_or_create(user=request.user, product=product)
    cart_item.quantity += quantity if not created else quantity
    cart_item.save()
    messages.success(request, f"{product.name} added to cart!")
    return redirect('storefront:cart_view')

# -----------------------------
# REMOVE FROM CART
# -----------------------------
@login_required
def cart_remove(request, pk):
    product = get_object_or_404(Product, pk=pk)
    CartItem.objects.filter(user=request.user, product=product).delete()
    messages.info(request, f"{product.name} removed from cart.")
    return redirect('storefront:cart_view')

# -----------------------------
# CHECKOUT
# -----------------------------
@login_required
def checkout(request):
    cart_items = CartItem.objects.filter(user=request.user)
    total_price = sum(item.subtotal() for item in cart_items)

    if request.method == 'POST':
        address = request.POST['address']
        payment_method = request.POST['payment_method']

        order = Order.objects.create(
            user=request.user,
            total_price=total_price,
            address=address,
            payment_method=payment_method,
            status='Processing'
        )

        for item in cart_items:
            OrderItem.objects.create(
                order=order,
                product=item.product,
                quantity=item.quantity,
                price=item.product.price
            )

        cart_items.delete()  # empty cart after order
        messages.success(request, "Order placed successfully!")
        return redirect('storefront:order_placed', order_id=order.id)

    return render(request, 'storefront/checkout.html', {'cart_items': cart_items, 'total_price': total_price})

# -----------------------------
# ORDER CONFIRMATION
# -----------------------------
@login_required
def order_placed(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    return render(request, 'storefront/order_placed.html', {'order': order})

# -----------------------------
# RECOMMENDATIONS (AI)
# -----------------------------
@login_required
def recommendations(request):
    recs = Recommendation.objects.filter(user=request.user).select_related('product')
    return render(request, 'storefront/recommendations.html', {'recommendations': recs})
