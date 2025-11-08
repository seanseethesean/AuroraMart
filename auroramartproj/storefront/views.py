from typing import Optional

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.views import LoginView, LogoutView
from django.db import transaction
from django.db.models import Q, F
from adminpanel.models import Product, Customer, PRODUCT_CATEGORY_CHOICES
from .models import CartItem, Order, OrderItem, Recommendation
from django.contrib.auth import login as auth_login
from .forms import OnboardingForm, ProfileUpdateForm, RegistrationForm


CATEGORY_SYNONYMS = {}
for value, label in PRODUCT_CATEGORY_CHOICES:
    variants = {
        value,
        label,
        label.lower(),
        label.upper(),
        label.replace('&', 'and'),
        label.replace('&', 'and').replace('  ', ' '),
    }
    CATEGORY_SYNONYMS[value] = {v.strip() for v in variants if v}

# Additional legacy aliases
CATEGORY_SYNONYMS.setdefault('hair', set()).update({'Beauty & Personal Care', 'Beauty', 'Hair and Beauty'})
CATEGORY_SYNONYMS.setdefault('home', set()).update({'Home & Kitchen', 'Home and Kitchen', 'Home And Kitchen', 'Home'})
CATEGORY_SYNONYMS.setdefault('sports', set()).update({'Sports & Outdoors', 'Sports and Outdoors', 'Sports'})
CATEGORY_SYNONYMS.setdefault('groceries', set()).update({'Groceries & Gourmet', 'Groceries'})
CATEGORY_SYNONYMS.setdefault('others', set()).update({'Other', 'others'})
CATEGORY_SYNONYMS.setdefault('toys', set()).update({'Toys', 'Toy', 'Games'})

# allow beauty alias to map to hair category for legacy data and URLs
hair_synonyms = CATEGORY_SYNONYMS.get('hair', set()).copy()
CATEGORY_SYNONYMS['beauty'] = hair_synonyms | {'beauty', 'Beauty'}

CATEGORY_LABELS = dict(PRODUCT_CATEGORY_CHOICES)
CATEGORY_DESCRIPTIONS = {
    'electronics': 'Headphones, peripherals, gadgets',
    'hair': 'Skincare and personal care picks',
    'fashion': 'Wardrobe essentials for every day',
    'sports': 'Fitness gear, outdoor must-haves',
    'home': 'Cookware, storage, and home comforts',
    'books': 'Bestsellers and thoughtful reads',
    'groceries': 'Snacks and pantry staples',
    'toys': 'Playtime favourites and gifts',
    'others': 'Unique finds beyond the usual aisles',
}
CANONICAL_SLUGS = set(CATEGORY_LABELS.keys())
ALIAS_TO_CANONICAL = {}

for key, synonyms in CATEGORY_SYNONYMS.items():
    if key in CANONICAL_SLUGS:
        canonical = key
    elif key == 'beauty':
        canonical = 'hair'
    else:
        canonical = None

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
        category_cards.append({
            'slug': slug,
            'label': display_category_name(slug) or label,
            'tagline': CATEGORY_DESCRIPTIONS.get(slug, 'Shop now'),
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
    qs = Product.objects.filter(stock__gt=0).order_by('name')

    q = request.GET.get('q') or ""
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

    return render(request, 'storefront/product_list.html', {
        'products': qs,
        'categories': category_list,
        'active_category': active_category or cat,
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
    cart_items = list(CartItem.objects.select_related('product').filter(user=request.user))
    if not cart_items:
        messages.info(request, "Your cart is empty.")
        return redirect('storefront:product_list')

    total_price = sum(item.subtotal() for item in cart_items)

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
                    price=item.product.price
                )
                Product.objects.filter(pk=item.product.pk).update(stock=F('stock') - item.quantity)

            CartItem.objects.filter(user=request.user).delete()  # empty cart after order

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
    if recs.exists():
        recommended_products = [rec.product for rec in recs if rec.product and rec.product.stock > 0]
        return render(request, 'storefront/recommendations.html', {
            'recommended_products': recommended_products,
            'recommendations': recs,
            'ml_based': False,
            'inferred_category': None,
        })

    # No DB recommendations — try ML helpers from adminpanel (lazy import)
    try:
        from adminpanel.ml_utils import predict_preferred_category_for_customer, recommend_products_from_rules
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

    canonical_predicted = resolve_category_slug(predicted_category)
    display_predicted = display_category_name(predicted_category)

    preferred_slugs = []
    if customer and getattr(customer, 'preferred_categories', ''):
        for raw in customer.preferred_categories.split(','):
            raw = raw.strip()
            if not raw:
                continue
            slug = resolve_category_slug(raw) or raw
            if slug not in preferred_slugs:
                preferred_slugs.append(slug)

    # Build basket SKUs from current cart
    try:
        cart_items = CartItem.objects.select_related('product').filter(user=request.user)
        basket_skus = [ci.product.sku for ci in cart_items if getattr(ci.product, 'sku', None)]
    except Exception:
        basket_skus = []

    recommended_product_ids = []
    try:
        raw_ids = recommend_products_from_rules(basket_skus, top_n=12)
        if raw_ids:
            recommended_product_ids = [str(sku) for sku in raw_ids if sku]
    except Exception:
        recommended_product_ids = []

    # Preserve order while removing duplicates
    seen_ids = set()
    ordered_ids = []
    for sku in recommended_product_ids:
        if sku not in seen_ids:
            seen_ids.add(sku)
            ordered_ids.append(sku)

    products_list = []
    if ordered_ids:
        qs = Product.objects.filter(stock__gt=0, sku__in=ordered_ids)
        lookup = {prod.sku: prod for prod in qs}
        products_list = [lookup[sku] for sku in ordered_ids if sku in lookup]

    fallback_sources = []
    for slug in preferred_slugs:
        if slug and slug not in fallback_sources:
            fallback_sources.append(slug)
    if canonical_predicted and canonical_predicted not in fallback_sources:
        fallback_sources.append(canonical_predicted)

    if not products_list:
        for slug in fallback_sources:
            resolved_slug = resolve_category_slug(slug) or slug
            fallback_qs = Product.objects.filter(stock__gt=0).filter(category_filter_q(resolved_slug)).order_by('-stock', 'name')[:8]
            if fallback_qs:
                products_list = list(fallback_qs)
                display_predicted = display_category_name(resolved_slug)
                break

    ml_based = bool(ordered_ids)

    return render(request, 'storefront/recommendations.html', {
        'recommended_products': products_list,
        'recommendations': recs,
        'inferred_category': display_predicted,
        'ml_based': ml_based
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


class StorefrontLogoutView(LogoutView):
    next_page = 'storefront:home'

    def dispatch(self, request, *args, **kwargs):
        messages.success(request, "You have been logged out.")
        return super().dispatch(request, *args, **kwargs)