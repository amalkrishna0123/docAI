from rest_framework import serializers
from django.contrib.auth.models import User
from .models import OTP, UserProfile


class OTPRequestSerializer(serializers.Serializer):
    """Serializer for OTP request"""
    email = serializers.EmailField()
    
    def validate_email(self, value):
        """Validate email format"""
        return value.lower()


class OTPVerifySerializer(serializers.Serializer):
    """Serializer for OTP verification"""
    email = serializers.EmailField()
    otp_code = serializers.CharField(max_length=10)
    
    def validate_email(self, value):
        """Validate email format"""
        return value.lower()


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model"""
    class Meta:
        model = User
        fields = ['id', 'email', 'username', 'first_name', 'last_name']
        read_only_fields = ['id']


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for User Profile"""
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = UserProfile
        fields = ['user', 'phone_number', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']
