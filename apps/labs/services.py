import jsonschema
from jsonschema import validate
from django.core.cache import cache
from django.core.exceptions import ValidationError



def get_category_schema(category_id: int) -> dict:
    """
    Fetches the JSON schema for a lab category.
    Uses Redis/Django cache to eliminate DB queries at scale.
    """
    cache_key = f"lab_category_schema:{category_id}"
    schema = cache.get(cache_key)
    
    if schema is None:
        from apps.labs.models import LabCategory
        try:
            category = LabCategory.objects.get(id=category_id, is_active=True)
            schema = category.dynamic_schema
            # Cache for 24 hours (86400 seconds)
            cache.set(cache_key, schema, timeout=86400)
        except LabCategory.DoesNotExist:
            return {}
            
    return schema


def validate_lab_data(category_id: int, data: dict) -> None:
    """
    Validates dynamic category data against the stored JSON Schema.
    Raises a Django ValidationError if the data structure is invalid.
    """
    schema = get_category_schema(category_id)
    
    if not schema:
        # If no schema is defined for this category, pass validation
        return

    try:
        validate(instance=data, schema=schema)
    except jsonschema.exceptions.ValidationError as err:
        # Raise standard Django ValidationError so Serializers/Forms catch it naturally
        raise ValidationError({"category_data": f"Invalid dynamic field: {err.message}"})