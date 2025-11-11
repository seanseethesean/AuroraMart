from __future__ import annotations

from typing import Optional
import logging

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db.models import Q

from adminpanel.models import Customer
from adminpanel import ml_utils
from storefront.models import CartItem, BasketHistory, OrderItem, Recommendation
from adminpanel.models import Product as AdminProduct  # not used but imported for clarity
from storefront.views import resolve_category_slug, display_category_name
from adminpanel.models import Product as AdminPanelProduct
from adminpanel.models import Product

logger = logging.getLogger(__name__)

User = get_user_model()


def _gather_basket_skus(user):
    skus = []
    try:
        cart_sku_qs = (
            CartItem.objects
            .filter(user=user, product__sku__isnull=False)
            .values_list('product__sku', flat=True)
        )
        skus.extend([sku for sku in cart_sku_qs if sku])
    except Exception:
        pass

    try:
        history_entries = (
            BasketHistory.objects
            .filter(user=user)
            .order_by('-created_at')[:10]
        )
        for snapshot in history_entries:
            items = snapshot.items or []
            if isinstance(items, (list, tuple)):
                skus.extend(str(sku) for sku in items if sku)
    except Exception:
        pass

    try:
        order_sku_qs = (
            OrderItem.objects
            .filter(order__user=user, product__sku__isnull=False)
            .order_by('-order__date_ordered')
            .values_list('product__sku', flat=True)[:25]
        )
        skus.extend([sku for sku in order_sku_qs if sku])
    except Exception:
        pass

    if skus:
        skus = [sku for sku in dict.fromkeys([str(sku).strip() for sku in skus if sku])]
        skus = skus[:50]
    return skus


class Command(BaseCommand):
    help = 'Trace recommendation sources for a given user (by --email or --user-id) and print the decision trace.'

    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, help='User email to trace')
        parser.add_argument('--user-id', type=int, help='User id to trace')
        parser.add_argument('--limit', type=int, default=8, help='Limit for fallback product lists')

    def handle(self, *args, **options):
        email = options.get('email')
        user_id = options.get('user_id')
        limit = options.get('limit') or 8

        if not email and not user_id:
            raise CommandError('You must provide --email or --user-id')

        user = None
        if email:
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                raise CommandError(f'No user found with email {email}')
            except User.MultipleObjectsReturned:
                users = User.objects.filter(email=email).order_by('id')
                user = users.first()
                self.stdout.write(self.style.WARNING(f'Multiple users found with email {email}. Using id={user.id}'))
        else:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                raise CommandError(f'No user found with id {user_id}')

        self.stdout.write(self.style.MIGRATE_HEADING(f'Tracing recommendations for user id={user.id} email={getattr(user, "email", None)}'))

        # Customer profile
        customer = getattr(user, 'customer', None)
        if not customer:
            self.stdout.write(self.style.WARNING('No Customer profile attached to this user.'))
        else:
            self.stdout.write('Customer profile:')
            fields = ['age', 'household_size', 'has_children', 'gender', 'monthly_income', 'education', 'occupation', 'marital_status', 'preferred_categories']
            for f in fields:
                val = getattr(customer, f, None)
                self.stdout.write(f'  {f}: {repr(val)}')

        # DB Recommendation rows
        recs = Recommendation.objects.filter(user=user).select_related('product').order_by('-generated_at')
        self.stdout.write(f'Found {recs.count()} Recommendation DB rows')
        for rec in recs[:10]:
            prod = rec.product
            self.stdout.write(f'  - {getattr(prod, "sku", None)} | {getattr(prod, "name", None)} | reason={rec.reason} at={rec.generated_at}')

        # Gather basket SKUs
        basket = _gather_basket_skus(user)
        self.stdout.write(f'Basket SKUs signal ({len(basket)}): {basket}')

        # Association rules recommendations (best-effort)
        try:
            ar_recs = ml_utils.recommend_products_from_rules(basket, top_n=12)
            self.stdout.write(f'Association-rules SKUs (raw): {ar_recs}')
            if ar_recs:
                # resolve to products if available
                from adminpanel.models import Product as Prod
                prods = Prod.objects.filter(sku__in=ar_recs)
                lookup = {p.sku: p for p in prods}
                out = [f'{sku} -> {lookup[sku].name if sku in lookup else "(not in DB)"}' for sku in ar_recs]
                for line in out:
                    self.stdout.write('  ' + line)
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Association rules check failed: {e}'))

        # ML predicted category
        try:
            predicted = ml_utils.predict_preferred_category_for_customer(customer)
            self.stdout.write(f'ML predicted category (raw): {repr(predicted)}')
            if predicted:
                slug = resolve_category_slug(predicted)
                self.stdout.write(f'  resolved slug: {repr(slug)} display: {repr(display_category_name(predicted))}')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'ML prediction failed: {e}'))

        # Inspect decision-tree model presence and expected features (diagnostic)
        try:
            models = ml_utils.load_models()
            dt = models.get('decision_tree')
            if dt is None:
                self.stdout.write(self.style.WARNING('Decision-tree artefact not found (adminpanel/models or adminpanel/mlmodels).'))
            else:
                self.stdout.write(self.style.MIGRATE_LABEL('Decision-tree model found.'))
                # print feature names if model provides them
                expected = None
                if hasattr(dt, 'feature_names_in_'):
                    try:
                        expected = list(dt.feature_names_in_)
                        self.stdout.write(f'  model.feature_names_in_ ({len(expected)}): {expected}')
                    except Exception:
                        self.stdout.write(self.style.WARNING('  failed reading model.feature_names_in_'))

                # Show the feature DataFrame we build for this customer so you can compare
                try:
                    df = ml_utils.customer_to_feature_df(customer, expected_columns=expected)
                    # print a compact representation
                    if not df.empty:
                        self.stdout.write('Customer feature vector (as dict):')
                        d = df.fillna(0).to_dict(orient='records')[0]
                        # sort keys for readability
                        for k in sorted(d.keys()):
                            self.stdout.write(f'  {k}: {d[k]}')
                    else:
                        self.stdout.write(self.style.WARNING('customer_to_feature_df returned empty DataFrame'))
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'Failed building feature DataFrame: {e}'))
        except Exception:
            # be quiet on diagnostics errors
            pass

        # Evaluate fallback candidate lists: ML predicted category and explicit profile
        fallback_sources = []
        if customer:
            if predicted:
                fallback_sources.append(predicted)
            pref = getattr(customer, 'preferred_categories', '') or ''
            if pref:
                for raw in pref.split(','):
                    raw = raw.strip()
                    if raw and raw not in fallback_sources:
                        fallback_sources.append(raw)

        for slug in fallback_sources:
            resolved_slug = resolve_category_slug(slug) or slug
            from storefront.views import category_filter_q
            qs = AdminPanelProduct.objects.filter(stock__gt=0).filter(category_filter_q(resolved_slug)).order_by('-stock', '-id')[:limit]
            self.stdout.write(self.style.MIGRATE_LABEL(f'Fallback results for {slug} (resolved {resolved_slug}): {qs.count()} products'))
            for p in qs:
                self.stdout.write(f'  - {p.sku} | {p.name} | category={p.category}')

        # Print short summary to help debug common causes
        self.stdout.write('\nSummary diagnostics:')
        if ar_recs:
            self.stdout.write(' - Association rules provided recommendations; check basket/history for seed SKUs and association model outputs.')
        elif predicted:
            self.stdout.write(' - No association-rule recs. ML predicted a category; the model or preprocessing may be misaligned with live customer attributes.')
        elif getattr(customer, 'preferred_categories', ''):
            self.stdout.write(' - No AR or ML recs. Explicit profile preferred_categories present; these supplied the fallback.')
        else:
            self.stdout.write(' - No AR, ML, or profile preferences. Recommendations use cheap category-based fallback or in-stock picks.')

        self.stdout.write(self.style.SUCCESS('Trace complete.'))
