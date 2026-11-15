from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver




def update_branch_item(branches, instance):
    from apps.labs.models import BranchItem
    for branch in branches:
        if BranchItem.objects.filter(lab=branch, not_real_std=True).count() >= 1:
            pass
        else:
            BranchItem.objects.create(lab=branch, standard=instance, not_real_std=True)
