from rest_framework import serializers
from apps.analysis.models import AnalysisJob, AnalysisResult, Page, Fact, Evidence, Website, PageType

class AnalysisJobCreateSerializer(serializers.Serializer):
    url = serializers.URLField(required=True, max_length=1000)
    objective = serializers.CharField(required=False, default='company_intelligence', max_length=100)
    target_page_types = serializers.ListField(
        child=serializers.ChoiceField(choices=PageType.choices),
        required=False,
        default=list
    )
    target_paths = serializers.ListField(
        child=serializers.CharField(max_length=200),
        required=False,
        default=list
    )
    max_pages = serializers.IntegerField(required=False, min_value=1, max_value=20)
    options = serializers.DictField(required=False, default=dict)

    def validate_url(self, value):
        from apps.crawler.normalizer import normalize_url
        norm = normalize_url(value)
        if not norm:
            raise serializers.ValidationError("Provided URL is not a valid HTTP or HTTPS address.")
        return norm

    def validate(self, attrs):
        # Merge top-level target configs into options dictionary
        options = dict(attrs.get('options', {}))
        if attrs.get('target_page_types'):
            options['target_page_types'] = attrs['target_page_types']
        if attrs.get('target_paths'):
            options['target_paths'] = attrs['target_paths']
        if attrs.get('max_pages'):
            options['max_pages'] = attrs['max_pages']
        attrs['options'] = options
        return attrs

class AnalysisResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalysisResult
        fields = [
            'structured_data',
            'conflicts',
            'missing_fields',
            'sources',
            'created_at',
            'updated_at',
        ]

class PageItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Page
        fields = ['url', 'normalized_url', 'page_type', 'title', 'quality_score', 'fetch_method']

class AnalysisJobDetailSerializer(serializers.ModelSerializer):
    domain = serializers.CharField(source='website.domain', read_only=True)
    root_url = serializers.CharField(source='website.root_url', read_only=True)
    result = AnalysisResultSerializer(read_only=True)
    pages = serializers.SerializerMethodField()

    class Meta:
        model = AnalysisJob
        fields = [
            'id',
            'domain',
            'root_url',
            'objective',
            'status',
            'error_code',
            'error_detail',
            'budget_usage',
            'options',
            'pages',
            'result',
            'created_at',
            'updated_at',
        ]

    def get_pages(self, obj):
        # Return pages analysed under this job
        pages = Page.objects.filter(analyses__job=obj).distinct()
        return PageItemSerializer(pages, many=True).data

class AnalysisJobListSerializer(serializers.ModelSerializer):
    domain = serializers.CharField(source='website.domain', read_only=True)

    class Meta:
        model = AnalysisJob
        fields = ['id', 'domain', 'objective', 'status', 'created_at']
