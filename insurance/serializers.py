from rest_framework import serializers
from .models import InsuranceApplication, InsurancePolicy, ChatMessage
from django.contrib.auth.models import User


class InsuranceApplicationSerializer(serializers.ModelSerializer):
    """Serializer for Insurance Application"""
    user_email = serializers.EmailField(source='user.email', read_only=True)
    is_valid_emirates_id = serializers.BooleanField(source='is_emirates_id_valid', read_only=True)
    
    class Meta:
        model = InsuranceApplication
        fields = [
            'id', 'user', 'user_email', 'language', 'application_type', 
            'dependent_type', 'salary_range', 'emirates_id', 'full_name',
            'date_of_birth', 'issuing_date', 'expiry_date', 'nationality',
            'gender', 'issuing_place', 'occupation', 'sponsor_name',
            'mobile_number','uid_number','visa_type', 'visa_status_date', 'emirates_id_document', 'status', 'chat_history',
            'is_valid_emirates_id', 'passport_document', 'visa_document',
            'passport_number', 'passport_expiry_date', 'passport_name', 'passport_dob', 'passport_nationality',
            'visa_number', 'visa_expiry_date', 'visa_full_name', 'visa_eid_number', 'visa_passport_number',
            'has_medical_conditions', 'maf_responses',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']
    
    def validate_emirates_id(self, value):
        """Ensure Emirates ID is unique per user"""
        user = self.context['request'].user
        
        # Check if Emirates ID already has an active policy
        existing_policy = InsurancePolicy.objects.filter(
            application__emirates_id=value,
            status='Active'
        ).exists()
        
        if existing_policy:
            raise serializers.ValidationError(
                "This Emirates ID already has an active insurance policy. Only one policy is allowed per Emirates ID."
            )
        
        return value

    def validate_uid_number(self, value):
        if not value or len(value.strip()) < 5:
            raise serializers.ValidationError("UID number is required.")
        return value


class InsurancePolicySerializer(serializers.ModelSerializer):
    """Serializer for Insurance Policy"""
    application = InsuranceApplicationSerializer(read_only=True)
    insured_name = serializers.CharField(source='application.full_name', read_only=True)
    emirates_id = serializers.CharField(source='application.emirates_id', read_only=True)
    
    class Meta:
        model = InsurancePolicy
        fields = [
            'id', 'application', 'policy_number', 'plan_name', 'plan_type',
            'premium_amount', 'status', 'issue_date', 'expiry_date',
            'insured_name', 'emirates_id', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ChatMessageSerializer(serializers.ModelSerializer):
    """Serializer for Chat Messages"""
    user_email = serializers.EmailField(source='user.email', read_only=True)
    
    class Meta:
        model = ChatMessage
        fields = [
            'id', 'user', 'user_email', 'message_type', 'content',
            'session_id', 'created_at'
        ]
        read_only_fields = ['id', 'user', 'created_at']


class OCRDataSerializer(serializers.Serializer):
    """Serializer for OCR extracted data"""
    emirates_id = serializers.CharField(max_length=50)
    full_name = serializers.CharField(max_length=200)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    issuing_date = serializers.DateField(required=False, allow_null=True)
    expiry_date = serializers.DateField()
    nationality = serializers.CharField(max_length=100)
    gender = serializers.ChoiceField(choices=['Male', 'Female'])
    issuing_place = serializers.CharField(max_length=100)
    occupation = serializers.CharField(max_length=200, required=False, allow_blank=True)
    sponsor_name = serializers.CharField(max_length=200, required=False, allow_blank=True, allow_null=True)


class PassportOCRDataSerializer(serializers.Serializer):
    """Serializer for Passport OCR extracted data"""
    passport_number = serializers.CharField(max_length=50)
    full_name = serializers.CharField(max_length=200, required=False, allow_null=True)
    expiry_date = serializers.DateField(required=False, allow_null=True)
    nationality = serializers.CharField(max_length=100, required=False, allow_null=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    issuing_date = serializers.DateField(required=False, allow_null=True)


class VisaOCRDataSerializer(serializers.Serializer):
    """Serializer for Visa OCR extracted data"""
    visa_number = serializers.CharField(max_length=50, required=False, allow_null=True)
    full_name = serializers.CharField(max_length=200, required=False, allow_null=True)
    expiry_date = serializers.DateField(required=False, allow_null=True)
    file_number = serializers.CharField(max_length=50, required=False, allow_null=True)
    emirates_id_number = serializers.CharField(max_length=50, required=False, allow_null=True)
    passport_number = serializers.CharField(max_length=50, required=False, allow_null=True)
    issuing_date = serializers.DateField(required=False, allow_null=True)
    profession = serializers.CharField(max_length=200, required=False, allow_null=True)
    family_head_employer = serializers.CharField(max_length=200, required=False, allow_null=True)


class ProductRecommendationSerializer(serializers.Serializer):
    """Serializer for insurance product recommendations"""
    plan_name = serializers.CharField()
    plan_type = serializers.ChoiceField(choices=['LSB', 'NLSB'])
    premium_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    description = serializers.CharField(required=False)
    url = serializers.URLField(required=False)
