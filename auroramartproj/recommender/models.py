from django.db import models
from products.models import Product

class Recommendation(models.Model):
    base_product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='base_recommendations')
    recommended_product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='recommended_with')
    confidence_score = models.FloatField()

    def __str__(self):
        return f"{self.base_product} → {self.recommended_product} ({self.confidence_score:.2f})"
