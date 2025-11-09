from __future__ import annotations

import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from adminpanel import models as admin_models


CATEGORY_MAP = {
    'automotive': 'automotive',
    'auto': 'automotive',
    'vehicle': 'automotive',
    'beauty & personal care': 'beauty_personal_care',
    'beauty and personal care': 'beauty_personal_care',
    'beauty personal care': 'beauty_personal_care',
    'personal care': 'beauty_personal_care',
    'books': 'books',
    'literature': 'books',
    'electronics': 'electronics',
    'electronics & gadgets': 'electronics',
    'smart devices': 'electronics',
    'fashion - men': 'fashion_men',
    'men fashion': 'fashion_men',
    'mens fashion': 'fashion_men',
    'fashion men': 'fashion_men',
    'fashion - women': 'fashion_women',
    'women fashion': 'fashion_women',
    'fashion women': 'fashion_women',
    'groceries & gourmet': 'groceries_gourmet',
    'groceries and gourmet': 'groceries_gourmet',
    'grocery': 'groceries_gourmet',
    'health': 'health',
    'wellness': 'health',
    'home & kitchen': 'home_kitchen',
    'home and kitchen': 'home_kitchen',
    'home appliances': 'home_kitchen',
    'pet supplies': 'pet_supplies',
    'pets': 'pet_supplies',
    'sports & outdoors': 'sports_outdoors',
    'sports and outdoors': 'sports_outdoors',
    'toys & games': 'toys_games',
    'toys and games': 'toys_games',
    'toy': 'toys_games',
    'other': 'other',
    'others': 'other',
}


class Command(BaseCommand):
    help = "Seed the Product catalogue from datasets/products_500.csv without overwriting existing images."

    def add_arguments(self, parser):
        parser.add_argument(
            '--csv',
            dest='csv_path',
            default='adminpanel/datasets/products_500.csv',
            help='Path to the product catalogue CSV (default: adminpanel/datasets/products_500.csv).',
        )

    def handle(self, *args, **options):
        csv_path = Path(options['csv_path']).resolve()
        if not csv_path.exists():
            raise CommandError(f'Product dataset not found at {csv_path}')

        rows, header_map = self._read_csv(csv_path)
        if not rows:
            self.stdout.write(self.style.WARNING(f'No rows found in {csv_path}. Nothing to seed.'))
            return

        sku_key = self._require_column(header_map, ['sku', 'sku code', 'Sku', 'Sku code'])
        name_key = self._require_column(header_map, ['product name', 'name'])
        description_key = header_map.get('product description') or header_map.get('description')
        category_key = header_map.get('product category') or header_map.get('category')
        stock_key = header_map.get('quantity on hand') or header_map.get('stock')
        reorder_key = header_map.get('reorder quantity') or header_map.get('reorder level')
        price_key = header_map.get('unit price') or header_map.get('price')
        rating_key = header_map.get('product rating') or header_map.get('rating')

        Product = admin_models.Product
        created = updated = skipped = 0
        total = len(rows)

        for index, row in enumerate(rows, start=1):
            raw_sku = self._clean_text(row.get(sku_key))
            if not raw_sku:
                skipped += 1
                continue

            defaults: dict[str, Any] = {
                'name': self._clean_text(row.get(name_key)) or raw_sku,
                'category': self._resolve_category(self._clean_text(row.get(category_key))),
                'price': self._parse_decimal(row.get(price_key)),
                'stock': self._parse_int(row.get(stock_key)),
                'description': self._clean_text(row.get(description_key)),
                'rating': self._parse_rating(row.get(rating_key)),
                'reorder_threshold': self._parse_int(row.get(reorder_key), allow_zero=False),
            }

            obj, was_created = Product.objects.update_or_create(
                sku=raw_sku,
                defaults=defaults,
            )

            if was_created:
                created += 1
            else:
                updated += 1

            if index % 50 == 0 or index == total:
                self.stdout.write(f"Processed {index}/{total} products…")

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded products from {csv_path}: created={created}, updated={updated}, skipped={skipped}"
            )
        )

    def _read_csv(self, csv_path: Path) -> tuple[list[dict[str, Any]], dict[str, str]]:
        try:
            with csv_path.open('r', encoding='utf-8', newline='') as handle:
                reader = csv.DictReader(handle)
                rows = list(reader)
                headers = reader.fieldnames or []
        except UnicodeDecodeError:
            with csv_path.open('r', encoding='latin-1', newline='') as handle:
                reader = csv.DictReader(handle)
                rows = list(reader)
                headers = reader.fieldnames or []

        header_map: dict[str, str] = {}
        for header in headers:
            if not header:
                continue
            header_map[header.strip().lower()] = header
        return rows, header_map

    def _require_column(self, header_map: dict[str, str], candidates: list[str]) -> str:
        for candidate in candidates:
            key = header_map.get(candidate.lower())
            if key:
                return key
        raise CommandError(f"Missing required column. Tried: {', '.join(candidates)}")

    def _clean_text(self, value: Any) -> str:
        if value is None:
            return ''
        return str(value).strip()

    def _resolve_category(self, raw: str) -> str:
        if not raw:
            return 'other'
        key = raw.lower()
        return CATEGORY_MAP.get(key, 'other')

    def _parse_decimal(self, value: Any) -> Decimal:
        if value is None or value == '':
            return Decimal('0')
        try:
            if isinstance(value, Decimal):
                return value
            text = str(value).replace('$', '').replace(',', '').strip()
            if not text:
                return Decimal('0')
            return Decimal(text)
        except (InvalidOperation, TypeError, ValueError):
            return Decimal('0')

    def _parse_int(self, value: Any, allow_zero: bool = True) -> int | None:
        if value is None or value == '':
            return 0 if allow_zero else None
        try:
            number = int(float(str(value).strip()))
            if number == 0 and not allow_zero:
                return None
            return max(number, 0)
        except (TypeError, ValueError):
            return 0 if allow_zero else None

    def _parse_rating(self, value: Any) -> Decimal | None:
        if value is None or value == '':
            return None
        try:
            text = str(value).strip()
            if not text:
                return None
            rating = Decimal(text)
            if rating < 0:
                return None
            return rating
        except (InvalidOperation, TypeError, ValueError):
            return None
