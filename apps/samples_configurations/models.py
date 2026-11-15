import uuid
from django.db import models
from django.core.validators import ValidationError, MaxValueValidator, MinValueValidator
from django.db.models import Q
from django.core.validators import FileExtensionValidator
from apps.utility.models import EquipmentType, Department, Trackable, Unit, GST, Brand
from django.utils.translation import gettext_lazy as _
from django.db import models, transaction

# from django.contrib.postgres.fields import ArrayField
# Create your models here.
PRICING_METHOD = (
    ("standard", 'Standard Wise'),
    ("parameter", 'Parameter Wise'),
)


class TestingType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    order = models.PositiveIntegerField(unique=True, default=0)

    def __str__(self):
        return f'{self.name}'

    class Meta:
        verbose_name = 'Testing Type'
        verbose_name_plural = 'Testing Types'
        default_permissions = ()


class SampleClauseCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    order = models.PositiveIntegerField(unique=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.name}'

    class Meta:
        verbose_name = 'Sample Clause Category'
        verbose_name_plural = 'Sample Clause Categories'
        default_permissions = ()


from datetime import date
def current_year():
    return date.today().year


class TestMethod(Trackable):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=500)
    lab = models.ForeignKey('labs.Branch', blank=True, null=True, on_delete=models.SET_NULL, related_name="test_methods")
    ref_no = models.CharField(max_length=100, blank=True, null=True)
    # order = models.PositiveIntegerField(unique=True)
    price = models.FloatField(default=1)
    year = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(1800),
            MaxValueValidator(current_year),
        ],
        null=True,
        blank=True
    )
    active = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.name}'

    class Meta:
        verbose_name = 'Test Method'
        verbose_name_plural = 'Test Methods'
        constraints = [
            models.UniqueConstraint(fields=['lab', 'name'], name='unique_lab_test_method')
        ]



class SampleClauseSubCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(
        SampleClauseCategory, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    order = models.PositiveIntegerField(unique=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.name}'

    class Meta:
        verbose_name = 'Sample Clause Sub Category'
        verbose_name_plural = 'Sample Clause Sub Categories'
        default_permissions = ()


class Category(models.Model):
    """
    Model for Item / Product / Standard Category
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    order = models.PositiveIntegerField(null=True, blank=True)
    active = models.BooleanField(default=True)
    image = models.ImageField(upload_to="product_categories/images/", null=True, blank=True)
    icon = models.FileField(
        upload_to="product_categories/icons/",
        null=True,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=['svg', 'png', 'jpg', 'jpeg', 'webp'])]
    )

    CATEGORY_TYPE_CHOICES = [
        ('Lims', 'Lims'),         
        ('Inventory', 'Inventory'),
        ('Equipment', 'Equipment'),
    ]
    category_type = models.CharField(
        max_length=20,
        choices=CATEGORY_TYPE_CHOICES,
        default='Lims'
    )

    def __str__(self):
        return f'{self.name}'

    class Meta:
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        default_permissions = ()


class SubCategory(models.Model):
    """
    Subcategory belonging to a Category
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='subcategories'
    )
    name = models.CharField(max_length=255)
    order = models.PositiveIntegerField(null=True, blank=True)
    active = models.BooleanField(default=True)
    image = models.ImageField(upload_to="product_subcategories/images/", null=True, blank=True)

    def __str__(self):
        return f'{self.name}'

    class Meta:
        verbose_name = 'Sub Category'
        verbose_name_plural = 'Sub Categories'
        default_permissions = ()


FORM_TYPE = (
    ('lims', _('Lims')),
    ('erp', _('Erp')),
)

ITEM_ROLE_CHOICES = [
    ('expense', _('Expense')),
    ('inventory', _('Inventory')),
    ('service', _('Service')),
    ('product', _('Product')),
]

ITEM_TYPE_CHOICES = [
    ('labor', _('Labor')),
    ('material', _('Material')),
    ('equipment', _('Equipment')),
    ('lumpsum', _('Lump Sum')),
    ('other', _('Other')),
]


class MasterItemMixins(models.Model):
    """
    Master Item Mixins Table used to store product or items for
    """
    REL_NAME_PREFIX = 'item'
    # master items form fields for erp start from here....
    sku = models.CharField(max_length=50, blank=True,
                           null=True, verbose_name=_('SKU Code'))
    upc = models.CharField(max_length=50, blank=True,
                           null=True, verbose_name=_('UPC Code'))
    name = models.CharField(max_length=255, null=True, blank=True)
    price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    item_role = models.CharField(
        max_length=10, choices=ITEM_ROLE_CHOICES, null=True, blank=True)
    item_type = models.CharField(
        max_length=15, choices=ITEM_TYPE_CHOICES, null=True, blank=True)
    for_inventory = models.BooleanField(verbose_name=_('Is an item for inventory'), default=False,
                                        help_text=_('It is an item you require for your inventory.'))

    is_product_or_service = models.BooleanField(verbose_name=_('Is a product or service.'), default=False,
                                                help_text=_(
                                                    'Is a product or service you sell or provide to customers.'
    ))

    sold_as_unit = models.BooleanField(default=False)
    # inventory_account = models.ForeignKey(
    #     'accounting.Account',
    #     null=True,
    #     blank=True,
    #     verbose_name=_('Inventory Account'),
    #     related_name=f'{REL_NAME_PREFIX}_inventory_account',
    #     help_text=_('Inventory account where cost will be capitalized.'),
    #     on_delete=models.RESTRICT)
    inventory_received = models.DecimalField(
        null=True,
        blank=True,
        decimal_places=3,
        max_digits=20,
        verbose_name=_('Total inventory received.'))
    inventory_received_value = models.DecimalField(
        null=True,
        blank=True,
        decimal_places=2,
        max_digits=20,
        verbose_name=_('Total value of inventory received.'))
    # cogs_account = models.ForeignKey(
    #     'accounting.Account',
    #     null=True,
    #     blank=True,
    #     verbose_name=_('COGS Account'),
    #     related_name=f'{REL_NAME_PREFIX}_cogs_account',
    #     help_text=_(
    #         'COGS account where cost will be recognized on Income Statement.'),
    #     on_delete=models.RESTRICT)
    # earnings_account = models.ForeignKey(
    #     'accounting.Account',
    #     null=True,
    #     blank=True,
    #     verbose_name=_('Earnings Account'),
    #     related_name=f'{REL_NAME_PREFIX}_earnings_account',
    #     help_text=_(
    #         'Earnings account where revenue will be recognized on Income Statement.'),
    #     on_delete=models.RESTRICT)
    # expense_account = models.ForeignKey(
    #     'accounting.Account',
    #     null=True,
    #     blank=True,
    #     verbose_name=_('Expense Account'),
    #     related_name=f'{REL_NAME_PREFIX}_expense_account',
    #     help_text=_(
    #         'Expense account where cost will be recognized on Income Statement.'),
    #     on_delete=models.RESTRICT)

    additional_info = models.JSONField(blank=True,
                                       null=True,
                                       default=dict,
                                       verbose_name=_('Item Additional Info'))
    maximum_quantity = models.IntegerField(blank=True, null=True)
    stock_adjustment_type = models.CharField(max_length=55, blank=True, null=True,
                                             choices=[('Transfer/Indent', 'Transfer/Indent'), ('Return', 'Return'),
                                                      ('Production', 'Production')])
    serial = models.CharField(max_length=255, blank=True, null=True)
    brand = models.ForeignKey(
        Brand, on_delete=models.SET_NULL, null=True, blank=True)
    material_code = models.CharField(max_length=255, blank=True, null=True)
    min_stock_level = models.DecimalField(
        max_digits=9, decimal_places=2, default=0)
    max_stock_level = models.DecimalField(
        max_digits=9, decimal_places=2, default=0)
    rule = models.CharField(max_length=10, choices=(
        ("lifo", "LIFO"), ("fifo", "FIFO")), blank=True, null=True)

    class Meta:
        abstract = True


class MasterItemManager(models.Manager):
    """
    A custom defined ItemModelManager that implement custom QuerySet methods related to the ItemModel
    """

    # def for_entity(self, entity_slug, user_model):
    #     """
    #     Returns a QuerySet of ItemModel associated with a specific EntityModel & UserModel.
    #     May pass an instance of EntityModel or a String representing the EntityModel slug.
    #
    #     Parameters
    #     ----------
    #     entity_slug: str or EntityModel
    #         The entity slug or EntityModel used for filtering the QuerySet.
    #     user_model
    #         The request UserModel to check for privileges.
    #
    #     Returns
    #     -------
    #     ItemModelQuerySet
    #         A Filtered ItemModelQuerySet.
    #     """
    #     qs = self.get_queryset()
    #     if isinstance(entity_slug, lazy_loader.get_entity_model()):
    #         return qs.filter(
    #             Q(entity=entity_slug) &
    #             (
    #                     Q(entity__managers__in=[user_model]) |
    #                     Q(entity__admin=user_model)
    #             )
    #         ).select_related('uom')
    #     return qs.filter(
    #         Q(entity__slug__exact=entity_slug) &
    #         (
    #                 Q(entity__managers__in=[user_model]) |
    #                 Q(entity__admin=user_model)
    #         )
    #     ).select_related('uom')

    def for_entity_active(self, entity_slug, user_model):
        """
        Returns a QuerySet of Active ItemModel associated with a specific EntityModel & UserModel.
        May pass an instance of EntityModel or a String representing the EntityModel slug.

        Parameters
        ----------
        entity_slug: str or EntityModel
            The entity slug or EntityModel used for filtering the QuerySet.
        user_model
            The request UserModel to check for privileges.

        Returns
        -------
        ItemModelQuerySet
            A Filtered ItemModelQuerySet.
        """
        qs = self.for_entity(entity_slug=entity_slug, user_model=user_model)
        return qs.filter(is_active=True)

    def for_invoice(self, entity_slug, user_model):
        """
        Returns a QuerySet of ItemModels that can only be used for InvoiceModels for a specific EntityModel &
        UserModel. These types of items qualify as products or services sold.
        May pass an instance of EntityModel or a String representing the EntityModel slug.

        Parameters
        ----------
        entity_slug: str or EntityModel
            The entity slug or EntityModel used for filtering the QuerySet.
        user_model
            The request UserModel to check for privileges.

        Returns
        -------
        ItemModelQuerySet
            A Filtered ItemModelQuerySet.
        """
        qs = self.for_entity_active(
            entity_slug=entity_slug, user_model=user_model)
        return qs.filter(is_product_or_service=True)

    def for_bill(self, entity_slug, user_model):
        """
        Returns a QuerySet of ItemModels that can only be used for BillModels for a specific EntityModel &
        UserModel. These types of items qualify as expenses or inventory purchases.
        May pass an instance of EntityModel or a String representing the EntityModel slug.

        Parameters
        ----------
        entity_slug: str or EntityModel
            The entity slug or EntityModel used for filtering the QuerySet.
        user_model
            The request UserModel to check for privileges.

        Returns
        -------
        ItemModelQuerySet
            A Filtered ItemModelQuerySet.
        """
        qs = self.for_entity_active(
            entity_slug=entity_slug, user_model=user_model)
        return qs.filter(
            (
                Q(is_product_or_service=False) &
                Q(for_inventory=False)
            ) |
            Q(for_inventory=True)
        )

    def for_po(self, entity_slug, user_model):
        """
        Returns a QuerySet of ItemModels that can only be used for PurchaseOrders for a specific EntityModel &
        UserModel. These types of items qualify as inventory purchases.
        May pass an instance of EntityModel or a String representing the EntityModel slug.

        Parameters
        ----------
        entity_slug: str or EntityModel
            The entity slug or EntityModel used for filtering the QuerySet.
        user_model
            The request UserModel to check for privileges.

        Returns
        -------
        ItemModelQuerySet
            A Filtered ItemModelQuerySet.
        """
        qs = self.for_entity(entity_slug=entity_slug, user_model=user_model)
        return qs.inventory_all()

    def for_estimate(self, entity_slug: str, user_model):
        """
        Returns a QuerySet of ItemModels that can only be used for EstimateModels for a specific EntityModel &
        UserModel. These types of items qualify as products.
        May pass an instance of EntityModel or a String representing the EntityModel slug.

        Parameters
        ----------
        entity_slug: str or EntityModel
            The entity slug or EntityModel used for filtering the QuerySet.
        user_model
            The request UserModel to check for privileges.

        Returns
        -------
        ItemModelQuerySet
            A Filtered ItemModelQuerySet.
        """
        qs = self.for_entity_active(
            entity_slug=entity_slug, user_model=user_model)
        return qs.products()


class MasterItemQuerySet(models.QuerySet):
    """
    A custom-defined ItemModelQuerySet that implements custom QuerySet methods related to the MasterItemModel.
    """

    def lims_items(self):
        """
        Filters the QuerySet to only active Master Item Table.

        Returns
        -------
        MasterItemQuerySet
            A QuerySet with applied filters.
        """
        return self.filter(form_type='lims')

    def erp_items(self):
        """
        Filters the QuerySet to only active Master Item Table.

        Returns
        -------
        MasterItemQuerySet
            A QuerySet with applied filters.
        """
        return self.filter(form_type='erp')

    def active(self):
        """
        Filters the QuerySet to only active Item Models.

        Returns
        -------
        ItemModelQuerySet
            A QuerySet with applied filters.
        """
        return self.filter(disable=False)

    def products(self):
        """
        Filters the QuerySet to ItemModels that only qualify as products.

        Returns
        -------
        ItemModelQuerySet
            A Filtered ItemModelQuerySet.
        """
        return self.filter(
            (
                Q(is_product_or_service=True) &
                Q(for_inventory=True)
            ) |
            Q(item_role='product')
        )

    def services(self):
        """
        Filters the QuerySet to ItemModels that only qualify as services.

        Returns
        -------
        ItemModelQuerySet
            A Filtered ItemModelQuerySet.
        """
        return self.filter(
            (
                Q(is_product_or_service=True) &
                Q(for_inventory=False)
            ) |
            Q(item_role='service')
        )

    def expenses(self):
        """
        Filters the QuerySet to ItemModels that only qualify as expenses.

        Returns
        -------
        ItemModelQuerySet
            A Filtered ItemModelQuerySet.
        """
        return self.filter(
            (
                Q(is_product_or_service=False) &
                Q(for_inventory=False)
            ) | Q(item_role='expense')
        )

    def inventory_wip(self):
        """
        Filters the QuerySet to ItemModels that only qualify as inventory.
        These types of items cannot be sold as they are not considered a finished product.

        Returns
        -------
        ItemModelQuerySet
            A Filtered ItemModelQuerySet.
        """
        return self.filter(
            (
                Q(is_product_or_service=False) &
                Q(for_inventory=True)
            ) | Q(item_role='inventory')
        )

    def inventory_all(self):
        """
        Filters the QuerySet to ItemModels that only qualify as inventory.
        These types of items may be finished or unfinished.


        Returns
        -------
        ItemModelQuerySet
            A Filtered ItemModelQuerySet.
        """
        return self.filter(
            (
                (
                    Q(is_product_or_service=False) &
                    Q(for_inventory=True)
                ) | Q(item_role='inventory')
            ) |
            (
                (
                    Q(is_product_or_service=True) &
                    Q(for_inventory=True)
                ) |
                Q(item_role='product')

            )
        )

    def bills(self):
        """
        Filters the QuerySet to ItemModels that are eligible only for bills..

        Returns
        -------
        ItemModelQuerySet
            A Filtered ItemModelQuerySet.
        """
        return self.filter(
            (
                Q(is_product_or_service=False) &
                Q(for_inventory=False)
            ) |
            Q(for_inventory=True)
        )

    def invoices(self):
        return self.filter(is_product_or_service=True)

    def estimates(self):
        return self.invoices()

    def purchase_orders(self):
        return self.inventory_all()



VALUE_TYPE = (
    ('1', 'Greater than'),
    ('2', 'Not more than'),
    ('3', 'Not less than'),
    ('4', 'Maximum'),
    ('5', 'Minimum'),
    ('6', 'In Range'),
    ('7', 'Not Applicable')
)


class ParameterRangeValue(Trackable):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    text = models.CharField(max_length=555, blank=True, null=True)
    value_type = models.CharField(
        max_length=20, choices=VALUE_TYPE, blank=True, null=True)
    range_min = models.CharField(max_length=255, blank=True, null=True)
    range_max = models.CharField(max_length=255, blank=True, null=True)
    range_val = models.FloatField(blank=True, null=True)
    desc = models.TextField(blank=True, null=True)

    def __str__(self):
        return "{}".format(self.range_val)


class ParameterQualitativeValue(Trackable):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    text = models.CharField(max_length=555, blank=True, null=True)
    value = models.CharField(max_length=100, blank=True, null=True)
    desc = models.TextField(blank=True, null=True)

    def __str__(self):
        return "{}".format(self.text)


class TRConfiguration(Trackable):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    show_custom_standard = models.BooleanField(
        default=False,
        help_text="Show custom standard while creating a Test request Quote"
    )
    is_payment_applicable = models.BooleanField(default=False)
    is_verification_required = models.BooleanField(default=False)
    is_sign_required = models.BooleanField(default=True)
    is_result_review_required = models.BooleanField(default=True)
    is_result_approval_required = models.BooleanField(default=True)
    is_report_verification_required = models.BooleanField(default=True)
    is_report_approval_required = models.BooleanField(default=True)
    is_report_verifier_signature_required = models.BooleanField(default=True)
    is_report_approver_signature_required = models.BooleanField(default=True)
    is_review_required = models.BooleanField(default=True)
    # it defines a new option to Lab In-charge to revert the submitted result for retesting again from scratch
    can_result_retested = models.BooleanField(default=True)
    # it defines a new option to Lab In-charge to revert the submitted result for editing again the result
    can_result_edited = models.BooleanField(default=True)
    can_upload_result_file = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Test Request Configuration'
        verbose_name_plural = 'Test Request Configurations'
        default_permissions = ()


class TermsCondition(Trackable):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, blank=True, null=True)
    terms_n_condition = models.TextField()
    active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(unique=True)

    def __str__(self):
        return "{}".format(self.terms_n_condition)




class ResultType(models.Model):
    TYPE = (
        ('text', _('Text')),
        ('date', _('Date')),
        ('float', _('Float')),
        ('int', _('Integer')),
        ('bool', _('True / False')),
        ('object', _('Django Object')),
        ('enum', _('Multiple Choice')),
        ('json', _('JSON Object')),
        ('csv', _('Comma-Separated-Value')),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True, null=True)
    type = models.CharField(max_length=50, choices=TYPE, null=True)
    active = models.BooleanField(default=True)

    class Meta:
        default_permissions = ()

    def __str__(self):
        return "{}".format(self.name)



class ServiceCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)

    class Meta:
        default_permissions = ()

    def __str__(self):
        return "{}".format(self.name)

############  Code for calibrationExcelSheet #########################

