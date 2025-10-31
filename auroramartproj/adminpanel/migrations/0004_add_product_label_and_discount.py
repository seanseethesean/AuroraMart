"""Add label and discount_percent to Product

Auto-generated migration-like file to be applied for repo consistency.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adminpanel', '0003_add_customer_phone_address'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='label',
            field=models.CharField(blank=True, choices=[('', 'None'), ('new', 'New Arrival'), ('discounted', 'Discounted'), ('last_pieces', 'Last Pieces')], default='', max_length=32),
        ),
        migrations.AddField(
            model_name='product',
            name='discount_percent',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Percent discount e.g. 10 for 10%', max_digits=5, null=True),
        ),
    ]
