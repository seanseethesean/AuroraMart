from typing import Optional
from functools import lru_cache
import logging
import os
from django.templatetags.static import static
import threading

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.views import LoginView, LogoutView
from django.db import transaction
from django.db.models import Q, F
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from adminpanel.models import Product, Customer, PRODUCT_CATEGORY_CHOICES
from .models import CartItem, Order, OrderItem, Recommendation, BasketHistory
from django.contrib.auth import login as auth_login
from .forms import OnboardingForm, ProfileUpdateForm, RegistrationForm
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import json
from datetime import datetime


EXTRA_CATEGORY_ALIASES = {
    'automotive': {'auto', 'vehicle', 'car care'},
    'beauty_personal_care': {'beauty', 'personal care', 'beauty personal care', 'hair', 'hair & beauty'},
    'fashion_men': {'mens fashion', "men's fashion", 'men fashion', 'fashion'},
    'fashion_women': {'womens fashion', "women's fashion", 'women fashion', 'fashion'},
    'groceries_gourmet': {'groceries', 'grocery'},
    'health': {'wellness'},
    'home_kitchen': {'home', 'kitchen'},
    'pet_supplies': {'pets', 'pet supply'},
    'sports_outdoors': {'sports', 'outdoors'},
    'toys_games': {'toys', 'games'},
    'other': {'others'},
}

CATEGORY_SYNONYMS = {}
for value, label in PRODUCT_CATEGORY_CHOICES:
    variants = {
        value,
        label,
        label.lower(),
        label.upper(),
        label.replace('&', 'and'),
        label.replace('&', 'and').replace('-', ' '),
        label.replace('-', ' '),
        label.replace('  ', ' '),
    }
    variants |= EXTRA_CATEGORY_ALIASES.get(value, set())
    CATEGORY_SYNONYMS[value] = {v.strip() for v in variants if v}

CATEGORY_LABELS = dict(PRODUCT_CATEGORY_CHOICES)
CATEGORY_DESCRIPTIONS = {
    'automotive': 'Auto care, accessories, and tools',
    'beauty_personal_care': 'Self-care, skincare, and grooming essentials',
    'books': 'Bestsellers, learning, and leisure reads',
    'electronics': 'Headphones, peripherals, and smart gadgets',
    'fashion_men': 'Menswear staples and style upgrades',
    'fashion_women': 'Womenswear for every occasion',
    'groceries_gourmet': 'Snacks, beverages, and pantry staples',
    'health': 'Wellness boosts and daily supplements',
    'home_kitchen': 'Cookware, decor, and home comforts',
    'pet_supplies': 'Everything to spoil your pets',
    'sports_outdoors': 'Gear up for fitness and adventures',
    'toys_games': 'Playtime favourites and family fun',
    'other': 'Unique finds beyond the usual aisles',
}
CANONICAL_SLUGS = set(CATEGORY_LABELS.keys())
ALIAS_TO_CANONICAL = {}

for key, synonyms in CATEGORY_SYNONYMS.items():
    canonical = key if key in CANONICAL_SLUGS else None
    if canonical is None:
        continue
    for alias in synonyms | {key}:
        ALIAS_TO_CANONICAL[alias.lower()] = canonical
    ALIAS_TO_CANONICAL[canonical.lower()] = canonical


def get_canonical_category_list():
    """Return ordered list of (slug, label) matching configured product categories."""
    seen = set()
    ordered = []
    for slug, label in PRODUCT_CATEGORY_CHOICES:
        if slug in seen:
            continue
        ordered.append((slug, label))
        seen.add(slug)
    return ordered


def resolve_category_slug(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    key = value.strip().lower()
    if key in ALIAS_TO_CANONICAL:
        return ALIAS_TO_CANONICAL[key]
    if key in CANONICAL_SLUGS:
        return key
    return None


def category_filter_q(slug: str) -> Q:
    aliases = CATEGORY_SYNONYMS.get(slug, {slug})
    query = Q()
    for alias in aliases:
        if alias:
            query |= Q(category__iexact=alias)
    if not query:
        query = Q(category__iexact=slug)
    return query


def display_category_name(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    slug = resolve_category_slug(value)
    if slug and slug in CATEGORY_LABELS:
        return CATEGORY_LABELS[slug]
    return value


ORDER_STATUS_SEQUENCE = [choice[0] for choice in Order.STATUS_CHOICES]


@lru_cache(maxsize=512)
def _cached_rule_suggestions(seed_tuple: tuple[str, ...], top_n: int) -> tuple[str, ...]:
    try:
        from adminpanel.ml_utils import recommend_products_from_rules
    except Exception:
        return tuple()

    try:
        return tuple(recommend_products_from_rules(list(seed_tuple), top_n=top_n))
    except Exception:
        return tuple()


def recommend_products_for_skus(seed_skus, *, exclude_skus=None, limit=4):
    """Helper to resolve Product objects from association-rule suggestions."""
    if not seed_skus:
        return []

    seen_seed = set()
    seed = []
    for sku in seed_skus:
        token = str(sku).strip()
        if not token or token in seen_seed:
            continue
        seed.append(token)
        seen_seed.add(token)
    if not seed:
        return []

    exclude = {str(s) for s in (exclude_skus or []) if s}

    raw_ids = _cached_rule_suggestions(tuple(seed), limit * 3)

    ordered_ids = []
    seen = set()
    for sku in raw_ids:
        key = str(sku)
        if not key or key in exclude or key in seen:
            continue
        ordered_ids.append(key)
        seen.add(key)
        if len(ordered_ids) >= limit:
            break

    if not ordered_ids:
        return []

    products = Product.objects.filter(stock__gt=0, sku__in=ordered_ids)
    lookup = {prod.sku: prod for prod in products}
    return [lookup[sku] for sku in ordered_ids if sku in lookup]


def record_basket_snapshot(user):
    """Persist a snapshot of the user's current cart SKUs for recommendation history."""
    if not getattr(user, 'is_authenticated', False):
        return

    skus = list(
        CartItem.objects
        .filter(user=user, product__sku__isnull=False)
        .values_list('product__sku', flat=True)
    )
    if not skus:
        return

    try:
        BasketHistory.objects.create(user=user, items=skus)
    except Exception:
        # Capture but do not block cart flows
        pass

# -----------------------------
# Log In
# -----------------------------
def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # ensure a Customer profile exists
            Customer.objects.get_or_create(user=user)
            auth_login(request, user)
            return redirect('storefront:onboarding')
    else:
        form = RegistrationForm()
    return render(request, 'storefront/register.html', {'form': form})

# -----------------------------
# HOME PAGE
# -----------------------------
def home(request):
    products = Product.objects.filter(stock__gt=0).order_by('-stock')[:8]  # show 8 featured in-stock items
    category_cards = []
    for slug, label in get_canonical_category_list():
        # Resolve a suitable image file for this category. Look in the app's static
        # images directory for files matching common basenames (slug, simplified slug,
        # or a small special-case map) with common image extensions.
        images_dir = os.path.join(settings.BASE_DIR, 'storefront', 'static', 'storefront', 'images')

        def find_image_for_slug(s):
            candidates = []
            # allow special-case friendly basenames
            special = {
                'beauty_personal_care': 'beauty',
                'groceries_gourmet': 'groceries',
                'home_kitchen': 'home',
                'pet_supplies': 'pet',
                'sports_outdoors': 'sports',
                'toys_games': 'toy',
                'other': 'others'
            }
            if s in special:
                candidates.append(special[s])
            # direct slug and a simplified token (first segment)
            candidates.append(s)
            first = s.split('_')[0]
            if first and first not in candidates:
                candidates.append(first)

            exts = ['.png', '.jpg', '.jpeg', '.webp', '.avif', '.svg']
            for base in candidates:
                for ext in exts:
                    fname = f"{base}{ext}"
                    path = os.path.join(images_dir, fname)
                    try:
                        if os.path.exists(path):
                            return static(f'storefront/images/{fname}')
                    except Exception:
                        # ignore filesystem issues and continue
                        continue
            # fallback placeholder
            try:
                return static('storefront/images/product_placeholder.svg')
            except Exception:
                return ''

        category_cards.append({
            'slug': slug,
            'label': display_category_name(slug) or label,
            'tagline': CATEGORY_DESCRIPTIONS.get(slug, 'Shop now'),
            'image': find_image_for_slug(slug),
        })
    return render(request, 'storefront/home.html', {
        'products': products,
        'category_cards': category_cards,
    })

# -----------------------------
# ONBOARDING
# -----------------------------
@login_required
def onboarding(request):
    customer = request.user.customer
    if request.method == 'POST':
        form = OnboardingForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            return redirect('storefront:recommendations')
    else:
        form = OnboardingForm(instance=customer)
    return render(request, 'storefront/onboarding.html', {'form': form})

# -----------------------------
# PRODUCT LIST
# -----------------------------
def product_list(request):
    qs = Product.objects.filter(stock__gt=0).order_by('-stock', '-id')

    q = (request.GET.get('q') or "").strip()
    cat = request.GET.get('cat') or ""

    if q:
        qs = qs.filter(
            Q(name__icontains=q) | Q(description__icontains=q) | Q(sku__icontains=q)
        ).distinct()
    active_category = None
    if cat:
        canonical = resolve_category_slug(cat)
        if canonical:
            qs = qs.filter(category_filter_q(canonical))
            active_category = display_category_name(canonical)
        else:
            qs = qs.filter(category__iexact=cat)
            active_category = display_category_name(cat)

    category_list = []
    for slug, label in get_canonical_category_list():
        display_label = display_category_name(slug) or label
        category_list.append((slug, display_label))

    paginator = Paginator(qs, 24)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    products_list = list(page_obj.object_list)

    base_querystring = request.GET.copy()
    base_querystring.pop('page', None)
    base_querystring = base_querystring.urlencode()

    page_range = list(page_obj.paginator.get_elided_page_range(number=page_obj.number, on_each_side=1, on_ends=1))

    return render(request, 'storefront/product_list.html', {
        'products': products_list,
        'categories': category_list,
        'active_category': active_category or cat,
        'page_obj': page_obj,
        'page_querystring': base_querystring,
        'page_range': page_range,
    })

# -----------------------------
# PRODUCT DETAIL
# -----------------------------
def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    # Try to surface association-rule suggestions using the viewed product as the seed SKU.
    suggestions = []
    try:
        if getattr(product, 'sku', None):
            suggestions = recommend_products_for_skus([product.sku], exclude_skus=[product.sku], limit=4)
    except Exception:
        # Fall back to same-category picks if the association model fails or is missing.
        suggestions = []

    if not suggestions:
        suggestions = (
            Product.objects
            .filter(stock__gt=0, category=product.category)
            .exclude(pk=product.pk)
            .order_by('-stock', '-id')[:4]
        )
    return render(request, 'storefront/product_detail.html', {
        'product': product,
        'frequently_bought': list(suggestions),
    })

# -----------------------------
# CART VIEW
# -----------------------------
@login_required
def cart_view(request):
    cart_items = list(CartItem.objects.select_related('product').filter(user=request.user))
    removed_names, adjusted_names = [], []

    for item in cart_items[:]:
        product = item.product
        stock_available = product.stock if product else 0
        if stock_available <= 0:
            removed_names.append(product.name if product else 'an item')
            item.delete()
            cart_items.remove(item)
            continue
        if item.quantity > stock_available:
            item.quantity = stock_available
            item.save(update_fields=['quantity'])
            adjusted_names.append(product.name)

    if removed_names:
        messages.warning(request, "Removed {} from your cart because they are out of stock.".format(
            ", ".join(sorted(set(removed_names)))
        ))
    if adjusted_names:
        messages.info(request, "Updated quantities for {} to match current stock.".format(
            ", ".join(sorted(set(adjusted_names)))
        ))

    # compute total and total savings using CartItem helpers
    from decimal import Decimal
    total_price = sum((item.subtotal() for item in cart_items), Decimal('0.00'))
    total_savings = sum((item.total_savings() for item in cart_items), Decimal('0.00'))
    cart_skus = [getattr(item.product, 'sku', None) for item in cart_items]
    cart_skus = [sku for sku in dict.fromkeys([sku for sku in cart_skus if sku])]
    cart_exclude = set(cart_skus)

    # Use any precomputed/manual Recommendation records first (very cheap DB lookup).
    # If none exist, avoid calling the potentially expensive ML helper synchronously on the
    # request path — instead spawn a background thread to compute and persist recommendations
    # for the user so subsequent requests are fast.
    complete_set = []
    try:
        manual_recs = (
            Recommendation.objects
            .filter(user=request.user)
            .select_related('product')
            .order_by('-generated_at')
        )
        manual_products = [rec.product for rec in manual_recs if getattr(rec.product, 'stock', 0) > 0]
        if manual_products:
            complete_set = manual_products[:4]
        else:
            # Kick off an asynchronous computation of recommendations and return the page
            # without waiting for it to complete so add-to-cart stays snappy.
            def _compute_and_store(user, skus, exclude_skus, limit=4):
                try:
                    products = recommend_products_for_skus(skus, exclude_skus=exclude_skus, limit=limit)
                    # Persist Recommendations (replace older ones)
                    if products:
                        # remove old recommendations for user
                        Recommendation.objects.filter(user=user).delete()
                        for p in products:
                            try:
                                Recommendation.objects.create(user=user, product=p, reason='association_rules')
                            except Exception:
                                # ignore per-item failures
                                pass
                except Exception:
                    # be quiet on failures — expensive ML helper may be missing or slow
                    pass

            if cart_skus:
                thread = threading.Thread(target=_compute_and_store, args=(request.user, cart_skus, cart_exclude), daemon=True)
                thread.start()
            # cheap fallback: pick up to 4 in-stock products excluding current cart SKUs
            fallback_qs = Product.objects.filter(stock__gt=0).exclude(sku__in=cart_exclude).order_by('-stock', '-id')[:4]
            complete_set = list(fallback_qs)
    except Exception:
        # Any error reading Recommendation table should not block the cart view; use cheap fallback
        try:
            fallback_qs = Product.objects.filter(stock__gt=0).exclude(sku__in=cart_exclude).order_by('-stock', '-id')[:4]
            complete_set = list(fallback_qs)
        except Exception:
            complete_set = []
    return render(request, 'storefront/cart.html', {
        'cart_items': cart_items,
        'total_price': total_price,
        'total': total_price,
        'total_savings': total_savings,
        'complete_the_set': complete_set,
    })


@login_required
def cart_update(request, pk):
    """Update quantity for a cart item. Supports set, increment, decrement actions."""
    if request.method != 'POST':
        return redirect('storefront:cart_view')

    action = request.POST.get('action')
    quantity = request.POST.get('quantity')
    cart_item = get_object_or_404(CartItem, user=request.user, product__pk=pk)
    product = cart_item.product
    stock_available = product.stock if product else 0

    if stock_available <= 0:
        cart_item.delete()
        messages.error(request, f"{product.name if product else 'Item'} is now out of stock and was removed from your cart.")
        return redirect('storefront:cart_view')

    if action == 'increment':
        if cart_item.quantity < stock_available:
            cart_item.quantity += 1
        else:
            messages.info(request, f"Only {stock_available} unit(s) of {product.name} available.")
    elif action == 'decrement':
        if cart_item.quantity > 1:
            cart_item.quantity -= 1
    elif quantity is not None:
        try:
            q = int(quantity)
            if q <= 0:
                cart_item.delete()
                messages.info(request, f"Removed {product.name} from your cart.")
                return redirect('storefront:cart_view')
            if q > stock_available:
                messages.info(request, f"Adjusted {product.name} to available stock ({stock_available}).")
                q = stock_available
            cart_item.quantity = q
        except ValueError:
            pass

    cart_item.save()
    record_basket_snapshot(request.user)
    return redirect('storefront:cart_view')

# -----------------------------
# ADD TO CART
# -----------------------------
@login_required
def cart_add(request, pk):
    product = get_object_or_404(Product, pk=pk)
    try:
        quantity = int(request.POST.get('quantity', 1))
    except (TypeError, ValueError):
        quantity = 1

    quantity = max(1, quantity)

    if product.stock <= 0:
        messages.error(request, f"{product.name} is currently out of stock.")
        return redirect('storefront:product_detail', pk=pk)

    if quantity > product.stock:
        messages.info(request, f"Only {product.stock} unit(s) of {product.name} available. Quantity adjusted.")
        quantity = product.stock

    cart_item, created = CartItem.objects.get_or_create(user=request.user, product=product)
    if created:
        cart_item.quantity = quantity
    else:
        new_quantity = cart_item.quantity + quantity
        if new_quantity > product.stock:
            new_quantity = product.stock
            messages.info(request, f"Your cart for {product.name} was capped at available stock ({product.stock}).")
        cart_item.quantity = new_quantity
    cart_item.save()
    record_basket_snapshot(request.user)
    messages.success(request, f"{product.name} added to cart!")
    return redirect('storefront:cart_view')

# -----------------------------
# REMOVE FROM CART
# -----------------------------
@login_required
def cart_remove(request, pk):
    product = get_object_or_404(Product, pk=pk)
    CartItem.objects.filter(user=request.user, product=product).delete()
    record_basket_snapshot(request.user)
    messages.info(request, f"{product.name} removed from cart.")
    return redirect('storefront:cart_view')

# -----------------------------
# CHECKOUT
# -----------------------------
@login_required
def checkout(request):
    cart_items = list(CartItem.objects.select_related('product').filter(user=request.user))
    if not cart_items:
        messages.info(request, "Your cart is empty.")
        return redirect('storefront:product_list')
    from decimal import Decimal
    total_price = sum((item.subtotal() for item in cart_items), Decimal('0.00'))
    total_savings = sum((item.total_savings() for item in cart_items), Decimal('0.00'))
    cart_skus = [getattr(item.product, 'sku', None) for item in cart_items]
    cart_skus = [sku for sku in dict.fromkeys([sku for sku in cart_skus if sku])]
    cart_exclude = set(cart_skus)
    complete_set = recommend_products_for_skus(cart_skus, exclude_skus=cart_exclude, limit=4)

    if request.method == 'POST':
        unavailable = []
        for item in cart_items:
            product = item.product
            available = product.stock if product else 0
            if available <= 0:
                unavailable.append((item, 0))
            elif item.quantity > available:
                unavailable.append((item, available))

        if unavailable:
            for item, available in unavailable:
                product = item.product
                if available <= 0:
                    messages.error(request, f"{product.name if product else 'An item'} is out of stock and was removed from your cart.")
                    item.delete()
                else:
                    item.quantity = available
                    item.save(update_fields=['quantity'])
                    messages.warning(request, f"Adjusted {product.name} quantity to {available} due to limited stock.")
            return redirect('storefront:cart_view')

        address = request.POST.get('address', '').strip()
        payment_method = request.POST.get('payment_method', '').strip()

        if not address or not payment_method:
            messages.error(request, "Please provide shipping address and payment method.")
            return redirect('storefront:checkout')

        # If paying by card (simple server-side validation), ensure basic card
        # fields look valid. We do NOT store card data — this is only to provide
        # basic client/server validation for the project exercise.
        if payment_method.lower() == 'card' or payment_method == 'Card':
            card_name = request.POST.get('card_name', '').strip()
            card_number = request.POST.get('card_number', '').replace(' ', '')
            card_expiry = request.POST.get('card_expiry', '').strip()
            card_cvv = request.POST.get('card_cvv', '').strip()

            # Basic validations
            if not card_name:
                messages.error(request, 'Please enter the name on the card.')
                return redirect('storefront:checkout')
            if not (card_number.isdigit() and len(card_number) == 16):
                messages.error(request, 'Card number must be 16 digits.')
                return redirect('storefront:checkout')
            if not (card_cvv.isdigit() and len(card_cvv) == 3):
                messages.error(request, 'CVV must be a 3-digit number.')
                return redirect('storefront:checkout')
            # expiry MM/YY
            try:
                parts = card_expiry.split('/')
                if len(parts) != 2:
                    raise ValueError('bad format')
                mm = int(parts[0])
                yy = int(parts[1])
                if mm < 1 or mm > 12:
                    raise ValueError('bad month')
                year = 2000 + yy if yy < 100 else yy
                now = datetime.utcnow()
                if year < now.year or (year == now.year and mm < now.month):
                    messages.error(request, 'Card has expired.')
                    return redirect('storefront:checkout')
            except Exception:
                messages.error(request, 'Expiry must be MM/YY and not expired.')
                return redirect('storefront:checkout')

        with transaction.atomic():
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
                    price=item.product.get_display_price()
                )
                Product.objects.filter(pk=item.product.pk).update(stock=F('stock') - item.quantity)

            record_basket_snapshot(request.user)

            CartItem.objects.filter(user=request.user).delete()  # empty cart after order

        messages.success(request, "Order placed successfully!")
        return redirect('storefront:order_placed', order_id=order.id)

    # If we don't have any ML-based suggestions, provide a cheap fallback so the UI
    # always has a 'Complete the set' section to show.
    if not complete_set:
        try:
            cart_exclude = set(cart_skus)
            fallback_qs = Product.objects.filter(stock__gt=0).exclude(sku__in=cart_exclude).order_by('-stock', '-id')[:4]
            complete_set = list(fallback_qs)
        except Exception:
            complete_set = []

    return render(request, 'storefront/checkout.html', {
        'cart_items': cart_items,
        'total_price': total_price,
        'total_cents': int(total_price * 100),
        'complete_the_set': complete_set,
    })


# Payment intents removed — payment is handled by server-side checkout POST.

# -----------------------------
# ORDER CONFIRMATION
# -----------------------------
@login_required
def order_placed(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    return render(request, 'storefront/order_placed.html', {'order': order})


# -----------------------------
# ORDERS OVERVIEW
# -----------------------------
@login_required
def order_list(request):
    orders = (
        Order.objects.filter(user=request.user)
        .prefetch_related('items__product')
        .order_by('-date_ordered')
    )

    max_index = max(len(ORDER_STATUS_SEQUENCE) - 1, 1)
    orders_payload = []
    for order in orders:
        items = list(order.items.all())
        try:
            progress_index = ORDER_STATUS_SEQUENCE.index(order.status)
        except ValueError:
            progress_index = 0
        progress_percent = int((progress_index / max_index) * 100) if max_index else 100
        orders_payload.append({
            'order': order,
            'items': items,
            'progress_index': progress_index,
            'progress_percent': progress_percent,
        })

    return render(request, 'storefront/orders.html', {
        'orders_payload': orders_payload,
        'status_sequence': ORDER_STATUS_SEQUENCE,
    })


@login_required
@require_POST
def order_confirm_delivery(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    if order.status != Order.STATUS_DELIVERED:
        order.mark_delivered()
        messages.success(request, f"Order #{order.id} marked as delivered. Thanks for confirming!")
    else:
        messages.info(request, f"Order #{order.id} is already recorded as delivered.")
    return redirect('storefront:order_list')

# -----------------------------
# RECOMMENDATIONS
# -----------------------------
@login_required
def recommendations(request):
    """Render recommendations for the logged-in user.

    This view returns any precomputed Recommendation records associated with the user.
    If no DB recommendations are present, it will try calling the adminpanel model helpers
    (which load models from `adminpanel/mlmodels/`). Failures are handled gracefully.
    """
    recs = Recommendation.objects.filter(user=request.user).select_related('product')
    manual_products = [rec.product for rec in recs if rec.product and rec.product.stock > 0]

    # No DB recommendations — try ML helpers from adminpanel (lazy import)
    try:
        from adminpanel.ml_utils import predict_preferred_category_for_customer
    except Exception:
        # ml_utils missing or dependencies not installed — render empty/DB fallback
        return render(request, 'storefront/recommendations.html', {
            'recommended_products': [],
            'recommendations': recs,
            'ml_based': False,
            'inferred_category': None,
        })

    # Predict category and association-rule recommendations (best-effort)
    customer = getattr(request.user, 'customer', None)
    predicted_category = None
    try:
        predicted_category = predict_preferred_category_for_customer(customer)
    except Exception:
        predicted_category = None

    # Try to resolve the model's prediction to a canonical slug. The model may return
    # a display label (e.g. 'Books') or a slug-like value; try several heuristics.
    canonical_predicted = resolve_category_slug(predicted_category)
    display_predicted = display_category_name(predicted_category)
    if predicted_category and not canonical_predicted:
        # Try matching against configured category labels (case-insensitive)
        pred_text = str(predicted_category).strip()
        for slug, label in CATEGORY_LABELS.items():
            if pred_text.lower() == str(label).strip().lower():
                canonical_predicted = slug
                display_predicted = label
                break
    # If still unresolved, try matching by replacing common separators
    if predicted_category and not canonical_predicted:
        pred_text = str(predicted_category).lower().replace('&', 'and').replace('-', ' ').strip()
        for slug, label in CATEGORY_LABELS.items():
            lab_text = str(label).lower().replace('&', 'and').replace('-', ' ').strip()
            if pred_text == lab_text:
                canonical_predicted = slug
                display_predicted = label
                break

    preferred_slugs = []
    if customer and getattr(customer, 'preferred_categories', ''):
        for raw in customer.preferred_categories.split(','):
            raw = raw.strip()
            if not raw:
                continue
            slug = resolve_category_slug(raw) or resolve_category_slug(display_category_name(raw)) or raw
            if slug and slug not in preferred_slugs:
                preferred_slugs.append(slug)

    # Determine if customer has enough structured profile data for the ML model.
    # Require several non-empty features so we skip DT predictions for near-empty profiles.
    customer_has_profile = False
    if customer:
        feature_candidates = {
            'age': getattr(customer, 'age', None),
            'gender': getattr(customer, 'gender', None),
            'employment_status': getattr(customer, 'employment_status', None),
            'occupation': getattr(customer, 'occupation', None),
            'education': getattr(customer, 'education', None),
            'household_size': getattr(customer, 'household_size', None),
            'has_children': getattr(customer, 'has_children', None),
            'monthly_income': getattr(customer, 'monthly_income', None),
        }

        def _is_meaningful(name, value):
            if value in (None, '', [], (), {}):
                return False
            if name in {'age', 'household_size'}:
                try:
                    return int(value) > 0
                except (TypeError, ValueError):
                    return False
            if name == 'has_children':
                return bool(value)
            return True

        filled_features = sum(1 for key, val in feature_candidates.items() if _is_meaningful(key, val))
        customer_has_profile = filled_features >= 3

    # If the model predicted a category and customer has profile data, prefer ML first.
    products_list = []
    recommendation_source = None
    ml_based = False
    if predicted_category and canonical_predicted and customer_has_profile:
        try:
            resolved_slug = canonical_predicted
            ml_qs = (
                Product.objects
                .filter(stock__gt=0)
                .filter(category_filter_q(resolved_slug))
                .order_by('-stock', '-id')[:8]
            )
        except Exception:
            ml_qs = []
        if ml_qs:
            products_list = list(ml_qs)
            display_predicted = display_category_name(resolved_slug)
            recommendation_source = 'ml_predicted'
            ml_based = True

    # If the customer has explicit preferred categories, use them as the primary
    # (unless ML already supplied results above).
    if not products_list and preferred_slugs:
        for slug in preferred_slugs:
            resolved_slug = resolve_category_slug(slug) or slug
            try:
                pref_qs = (
                    Product.objects
                    .filter(stock__gt=0)
                    .filter(category_filter_q(resolved_slug))
                    .order_by('-stock', '-id')[:8]
                )
            except Exception:
                pref_qs = []
            if pref_qs:
                products_list = list(pref_qs)
                display_predicted = display_category_name(resolved_slug)
                recommendation_source = 'profile'
                ml_based = False
                break

    # Build SKU signal from current cart and recent basket history snapshots
    basket_skus: list[str] = []
    try:
        cart_sku_qs = (
            CartItem.objects
            .filter(user=request.user, product__sku__isnull=False)
            .values_list('product__sku', flat=True)
        )
        basket_skus.extend([sku for sku in cart_sku_qs if sku])
    except Exception:
        pass

    try:
        history_entries = (
            BasketHistory.objects
            .filter(user=request.user)
            .order_by('-created_at')[:10]
        )
        for snapshot in history_entries:
            items = snapshot.items or []
            if isinstance(items, (list, tuple)):
                basket_skus.extend(str(sku) for sku in items if sku)
    except Exception:
        pass

    try:
        order_sku_qs = (
            OrderItem.objects
            .filter(order__user=request.user, product__sku__isnull=False)
            .order_by('-order__date_ordered')
            .values_list('product__sku', flat=True)[:25]
        )
        basket_skus.extend([sku for sku in order_sku_qs if sku])
    except Exception:
        pass

    if basket_skus:
        basket_skus = [sku for sku in dict.fromkeys([str(sku).strip() for sku in basket_skus if sku])]
        basket_skus = basket_skus[:50]

    recommended_product_ids: list[str] = []
    if basket_skus:
        raw_ids = _cached_rule_suggestions(tuple(basket_skus), 12)
        if raw_ids:
            recommended_product_ids = [str(sku).strip() for sku in raw_ids if sku]

    # Preserve order while removing duplicates
    seen_ids = set()
    ordered_ids = []
    for sku in recommended_product_ids:
        if sku not in seen_ids:
            seen_ids.add(sku)
            ordered_ids.append(sku)

    # If profile already produced results above, keep them. Otherwise consider
    # association-rules suggestions derived from basket history.
    association_products: list[Product] = []
    if ordered_ids:
        qs = Product.objects.filter(stock__gt=0, sku__in=ordered_ids)
        lookup = {prod.sku: prod for prod in qs}
        association_products = [lookup[sku] for sku in ordered_ids if sku in lookup]

    if association_products:
        products_list = association_products
        recommendation_source = 'association_rules'

    # Prioritize ML predicted category for cold-starts: try the model's prediction first,
    # then fall back to explicit profile preferences.
    fallback_sources = []
    if canonical_predicted and customer_has_profile:
        fallback_sources.append(canonical_predicted)
    for slug in preferred_slugs:
        if slug and slug not in fallback_sources:
            fallback_sources.append(slug)

    if not products_list and manual_products:
        products_list = manual_products
        ml_based = False
        recommendation_source = 'manual'

    if not products_list:
        for slug in fallback_sources:
            resolved_slug = resolve_category_slug(slug) or slug
            fallback_qs = (
                Product.objects
                .filter(stock__gt=0)
                .filter(category_filter_q(resolved_slug))
                .order_by('-stock', '-id')[:8]
            )
            if fallback_qs:
                products_list = list(fallback_qs)
                display_predicted = display_category_name(resolved_slug)
                # Determine which fallback source produced these results
                if slug in preferred_slugs:
                    recommendation_source = 'profile'
                elif canonical_predicted and slug == canonical_predicted:
                    recommendation_source = 'ml_predicted'
                else:
                    recommendation_source = 'fallback'
                break

    # Flag whether the final recommendations came from ML sources (DT or association rules)
    ml_based = recommendation_source in {'ml_predicted', 'association_rules'}

    # Align displayed predicted category with the chosen recommendations to avoid mismatches
    try:
        if recommendation_source == 'association_rules' and products_list:
            # derive display category from the first recommended product
            display_predicted = display_category_name(getattr(products_list[0], 'category', None))
        elif recommendation_source == 'manual' and products_list:
            # manual recommendations may be product-specific; derive category from first product
            display_predicted = display_category_name(getattr(products_list[0], 'category', None))
    except Exception:
        # keep existing display_predicted in case of error
        pass

    # Log which source we used for recommendations
    logger = logging.getLogger(__name__)
    logger.info("Recommendations source for user %s: %s (predicted=%s)", getattr(request.user, 'id', None), recommendation_source, canonical_predicted)
    # Also print to stdout so it's visible in the terminal when running the dev server
    try:
        user_id = getattr(request.user, 'id', None)
        product_skus = [getattr(p, 'sku', None) for p in products_list]
        print(f"[recommendations] user={user_id} source={recommendation_source} predicted={canonical_predicted} products={product_skus}")
    except Exception:
        pass

    return render(request, 'storefront/recommendations.html', {
        'recommended_products': products_list,
        'recommendations': recs,
        'inferred_category': display_predicted,
        'ml_based': ml_based,
        'recommendation_source': recommendation_source,
    })


# -----------------------------
# PROFILE UPDATE
# -----------------------------
@login_required
def profile(request):
    customer = getattr(request.user, 'customer', None)
    if customer is None:
        messages.error(request, "Customer profile not found.")
        return redirect('storefront:home')

    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect('storefront:profile')
    else:
        form = ProfileUpdateForm(instance=customer)

    return render(request, 'storefront/profile.html', {'form': form})


class StorefrontLoginView(LoginView):
    template_name = 'storefront/login.html'

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Logged in successfully.")
        return response

    def form_invalid(self, form):
        """Provide clearer messages for invalid login attempts.

        If the username does not exist, show a specific message. Otherwise show
        a generic invalid credentials message.
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()
        username = self.request.POST.get('username')
        if username:
            try:
                User.objects.get(username=username)
                messages.error(self.request, 'Invalid username/password combination.')
            except User.DoesNotExist:
                messages.error(self.request, 'User not found. Please register or check your username.')
        else:
            messages.error(self.request, 'Please enter your username.')
        return super().form_invalid(form)


class StorefrontLogoutView(LogoutView):
    next_page = 'storefront:home'

    def dispatch(self, request, *args, **kwargs):
        messages.success(request, "You have been logged out.")
        return super().dispatch(request, *args, **kwargs)