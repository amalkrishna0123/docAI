from django.contrib import admin
from .models import InsuranceApplication, InsurancePolicy, ChatMessage


@admin.register(InsuranceApplication)
class InsuranceApplicationAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'full_name', 'emirates_id', 'application_type', 
        'issuing_place', 'salary_range', 'status', 'created_at'
    ]
    list_filter = ['status', 'application_type', 'gender', 'issuing_place', 'created_at']
    search_fields = ['emirates_id', 'full_name', 'user__email', 'mobile_number']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Application Info', {
            'fields': ('user', 'language', 'application_type', 'dependent_type', 'salary_range', 'status')
        }),
        ('Personal Details', {
            'fields': ('emirates_id', 'full_name', 'date_of_birth', 'gender', 'nationality', 'occupation')
        }),
        ('Emirates ID Details', {
            'fields': ('issuing_date', 'expiry_date', 'issuing_place', 'employer_sponsor_name')
        }),
        ('Contact', {
            'fields': ('mobile_number',)
        }),
        ('Documents', {
            'fields': ('emirates_id_document',)
        }),
        ('Chat History', {
            'fields': ('chat_history',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('user')


@admin.register(InsurancePolicy)
class InsurancePolicyAdmin(admin.ModelAdmin):
    list_display = [
        'policy_number', 'get_insured_name', 'plan_name', 
        'plan_type', 'premium_amount', 'status', 'issue_date', 'expiry_date'
    ]
    list_filter = ['status', 'plan_type', 'issue_date', 'expiry_date']
    search_fields = ['policy_number', 'application__full_name', 'application__emirates_id']
    readonly_fields = ['created_at', 'updated_at', 'issue_date']
    
    fieldsets = (
        ('Policy Details', {
            'fields': ('application', 'policy_number', 'plan_name', 'plan_type', 'premium_amount')
        }),
        ('Status & Dates', {
            'fields': ('status', 'issue_date', 'expiry_date')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_insured_name(self, obj):
        return obj.application.full_name
    get_insured_name.short_description = 'Insured Name'
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('application', 'application__user')


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'message_type', 'session_id', 'created_at', 'content_preview']
    list_filter = ['message_type', 'created_at']
    search_fields = ['user__email', 'session_id', 'content']
    readonly_fields = ['created_at']
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content Preview'
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('user')
