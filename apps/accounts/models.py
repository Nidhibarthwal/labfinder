from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class OTPVerification(models.Model):

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        VERIFIED = "VERIFIED", "Verified"
        EXPIRED = "EXPIRED", "Expired"
        INVALIDATED = "INVALIDATED", "Invalidated"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="otp_verifications",
    )

    email = models.EmailField(db_index=True)
    otp_code = models.CharField(max_length=5)
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )

    def is_expired(self):
        return timezone.now() >= (
            self.created_at + timedelta(minutes=5)
        )

    def __str__(self):
        return f"OTP for {self.email}"