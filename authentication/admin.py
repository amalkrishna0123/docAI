from django.contrib import admin
from .models import OTP, UserProfile


@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = ['email', 'otp_code', 'created_at', 'is_verified']
    list_filter = ['is_verified', 'created_at']
    search_fields = ['email', 'otp_code']
    readonly_fields = ['created_at']
    ordering = ['-created_at']


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone_number', 'created_at']
    search_fields = ['user__email', 'user__username', 'phone_number']
    readonly_fields = ['created_at', 'updated_at']
