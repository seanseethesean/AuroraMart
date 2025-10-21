from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from products.models import Product
from customers.models import Customer
from orders.models import Order, OrderItem

def home(request):
    return render(request, 'storefront/home.html')

def product_list(request):
    qs = Product.objects.select_related('category').order_by('name')
    return render(request, 'storefront/product_list.html', {'products': qs})

def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    return render(request, 'storefront/product_detail.html', {'product': product})

def _get_cart(session):
    return session.setdefault('cart', {})  # {product_id: qty}

def cart_view(request):
    cart = _get_cart(request.session)
    items, total = [], 0
    for pid, qty in cart.items():
        p = Product.objects.get(pk=pid)
        subtotal = p.price * qty
        items.append({'product': p, 'qty': qty, 'subtotal': subtotal})
        total += subtotal
    return render(request, 'storefront/cart.html', {'items': items, 'total': total})

def cart_add(request, pk):
    cart = _get_cart(request.session)
    cart[str(pk)] = cart.get(str(pk), 0) + 1
    request.session.modified = True
    messages.success(request, 'Added to cart.')
    return redirect('storefront:cart_view')

def cart_remove(request, pk):
    cart = _get_cart(request.session)
    cart.pop(str(pk), None)
    request.session.modified = True
    return redirect('storefront:cart_view')

@transaction.atomic
def checkout(request):
    cart = _get_cart(request.session)
    if not cart:
        messages.warning(request, 'Your cart is empty.')
        return redirect('storefront:product_list')

    # For now, attach the first customer or a placeholder guest flow
    customer = Customer.objects.first()  # replace with logged-in mapping later

    order = Order.objects.create(customer=customer, status='pending', total_price=0)
    total = 0
    for pid, qty in cart.items():
        p = Product.objects.select_for_update().get(pk=pid)
        OrderItem.objects.create(order=order, product=p, quantity=qty, subtotal=p.price * qty)
        p.stock = max(0, p.stock - qty)
        p.save(update_fields=['stock'])
        total += p.price * qty

    order.total_price = total
    order.save(update_fields=['total_price'])

    # clear cart
    request.session['cart'] = {}
    request.session.modified = True
    return redirect('storefront:order_placed', order_id=order.id)

def order_placed(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    return render(request, 'storefront/order_placed.html', {'order': order})
