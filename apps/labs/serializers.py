from rest_framework import serializers

from apps.labs.models import Branch, LabWebPage


class LabWebPageTreeSerializer(serializers.Serializer):
    """Recursive serializer to handle pages and nested sub-pages/submenus."""
    url = serializers.URLField(required=True)
    normalized_url = serializers.URLField(required=False, allow_null=True, allow_blank=True)
    title = serializers.CharField(required=True)
    page_type = serializers.CharField(required=False, default='OTHER')
    quality_score = serializers.FloatField(required=False, default=0.0)
    fetch_method = serializers.CharField(required=False, default='HTTP')
    pages = serializers.ListField(child=serializers.DictField(), required=False, default=list)


class LabCrawlerImportSerializer(serializers.Serializer):
    id = serializers.UUIDField(required=False)
    domain = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    root_url = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    status = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    pages = serializers.ListField(child=serializers.DictField(), required=False, default=list)
    result = serializers.DictField(required=True)

    def validate_result(self, value):
        if 'structured_data' not in value:
            raise serializers.ValidationError("Missing 'structured_data' key inside 'result' payload dictionary.")
        return value


class SubmenuSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabWebPage
        fields = ['id', 'title', 'slug', 'url', 'page_type', 'menu_order']


class LabMenuTreeSerializer(serializers.ModelSerializer):
    submenus = SubmenuSerializer(many=True, read_only=True)

    class Meta:
        model = LabWebPage
        fields = ['id', 'title', 'slug', 'url', 'page_type', 'menu_order', 'submenus']


class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        exclude = ['created_at', 'updated_at', 'created_by', 'updated_by']