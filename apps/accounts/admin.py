from django.contrib import admin

from apps.accounts.models import OTPVerification


# Register your models here.

@admin.register(OTPVerification)
class OTPVerificationAdmin(admin.ModelAdmin):
    list_display = ['id', 'email', 'otp_code', 'attempts', 'status', 'verified_at', 'created_at']
    list_filter = ['status',]
    search_fields = ['email', 'otp_code']