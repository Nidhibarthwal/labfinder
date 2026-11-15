# apps/customers/admin.py
from django.contrib import admin
from .models import CustomerDetails, LabPayLater


@admin.register(CustomerDetails)
class CustomerDetailsAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'company_name', 'profile')
    search_fields = (
        'first_name', 'last_name', 'company_name',
        'profile__user__username', 'profile__user__email',
    )
    raw_id_fields = ('profile',)
    readonly_fields = ('id',)


@admin.register(LabPayLater)
class LabPayLaterAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'lab', 'customer', 'pay_later_allowed')
    list_filter = ('pay_later_allowed',)
    search_fields = ('lab__lab_name', 'customer__first_name', 'customer__last_name', 'customer__profile__user__username')
    raw_id_fields = ('lab', 'customer')
    readonly_fields = ('id',)
