# signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.cache import cache
from .models import LabCategory

@receiver(post_save, sender=LabCategory)
def invalidate_category_schema_cache(sender, instance, **kwargs):
    cache_key = f"lab_category_schema:{instance.id}"
    cache.delete(cache_key)