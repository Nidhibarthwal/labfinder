from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver

from apps.labs.models import Branch
from apps.seo.services import sync_lab_seo


@receiver(post_save, sender=Branch)
def on_branch_save_sync_seo(sender, instance, created, **kwargs):
    """
    Auto-triggers when a laboratory is created or updated.
    Syncs category & location landing page metrics.
    """
    try:
        sync_lab_seo(instance)
    except Exception:
        pass


@receiver(m2m_changed, sender=Branch.categories.through)
def on_branch_categories_changed_sync_seo(sender, instance, action, **kwargs):
    """
    Auto-triggers when categories are attached or modified for a lab.
    """
    if action in ("post_add", "post_remove", "post_clear"):
        try:
            sync_lab_seo(instance)
        except Exception:
            pass
