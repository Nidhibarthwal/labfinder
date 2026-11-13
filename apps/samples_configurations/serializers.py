from apps.samples_configurations.models import TRConfiguration
from rest_framework import serializers
from apps.samples.utility import method_test_list_data
from apps.labs.models import BranchItem
from apps.samples_configurations.models import TestMethod, TermsCondition, ParameterRangeValue,Category
from django.core.exceptions import ValidationError



##########################################################################






class TestMethodSerializer(serializers.ModelSerializer):
    """
    TestMethodSerializer serializes the data of TestMethod Table
    """

    class Meta:
        model = TestMethod
        fields = "__all__"


class TermsConditionSerializer(serializers.ModelSerializer):
    """
    TermsConditionSerializer serializes the data of TermsCondition Table
    """

    class Meta:
        model = TermsCondition
        fields = "__all__"


class ParameterRangeValueSerializer(serializers.ModelSerializer):
    """
    ParameterRangeValueSerializer serializes the data of ParameterRangeValue Table
    """

    class Meta:
        model = ParameterRangeValue
        fields = "__all__"

#########################################################################

class CategorySerializer(serializers.ModelSerializer):

    class Meta:
        model = Category
        fields = "__all__"    


class TRConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = TRConfiguration
        fields = '__all__'