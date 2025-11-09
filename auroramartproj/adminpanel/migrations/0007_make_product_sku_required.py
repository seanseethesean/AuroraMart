import uuid

from django.db import migrations, models
from django.db.models import Q


def populate_missing_skus(apps, schema_editor):
    Product = apps.get_model('adminpanel', 'Product')
    existing = set(
        Product.objects.exclude(sku__isnull=True).exclude(sku__exact='').values_list('sku', flat=True)
    )
    for product in Product.objects.filter(Q(sku__isnull=True) | Q(sku__exact='')):
        base = f"MISSING-{product.pk or uuid.uuid4().hex[:6].upper()}"
        candidate = base
        suffix = 1
        while candidate in existing:
            candidate = f"{base}-{suffix}"
            suffix += 1
        product.sku = candidate
        product.save(update_fields=['sku'])
        existing.add(candidate)


class Migration(migrations.Migration):

    dependencies = [
        ('adminpanel', '0006_alter_product_image'),
    ]

    operations = [
        migrations.RunPython(populate_missing_skus, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='product',
            name='sku',
            field=models.CharField(help_text='Unique product identifier', max_length=50, unique=True),
        ),
    ]
