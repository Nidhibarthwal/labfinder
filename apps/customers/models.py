import uuid
from django.db import models
from apps.utility.models import Profile
from apps.labs.models import Branch


class CustomerDetails(models.Model):
    """Stub — flesh out to match Vista's real CustomerDetails if you have it."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.OneToOneField(Profile, on_delete=models.CASCADE, related_name='customer_user')
    first_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100, blank=True, null=True)
    company_name = models.CharField(max_length=200, blank=True, null=True)

    def __str__(self):
        return f'{self.first_name} {self.last_name}'.strip() or str(self.id)


class LabPayLater(models.Model):
    """Vista's LabCustomerPayLater, retargeted to Lab."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lab = models.ForeignKey(Branch, on_delete=models.CASCADE)
    customer = models.ForeignKey(CustomerDetails, on_delete=models.CASCADE, related_name='customer_pay')
    pay_later_allowed = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Lab Customer PayLater'
        verbose_name_plural = 'Lab Customers PayLater'
        default_permissions = ()

    def __str__(self):
        return self.customer.profile.user.username