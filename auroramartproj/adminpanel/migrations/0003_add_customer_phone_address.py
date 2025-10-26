# Generated migration to add phone and address to Customer
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adminpanel', '0002_remove_product_created_at_remove_product_sku_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='phone',
            field=models.CharField(max_length=30, blank=True),
        ),
        migrations.AddField(
            model_name='customer',
            name='address',
            field=models.TextField(blank=True),
        ),
    ]
