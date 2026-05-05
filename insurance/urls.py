from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    InsuranceApplicationViewSet,
    InsurancePolicyViewSet,
    ChatMessageViewSet,
    ProcessOCRView,
    ProcessPassportOCRView,
    ProcessVisaOCRView,
    GetProductRecommendationsView,
    CreatePolicyView
)

app_name = 'insurance'

# Create router for viewsets
router = DefaultRouter()
router.register(r'applications', InsuranceApplicationViewSet, basename='application')
router.register(r'policies', InsurancePolicyViewSet, basename='policy')
router.register(r'chat', ChatMessageViewSet, basename='chat')

urlpatterns = [
    # ViewSet routes
    path('', include(router.urls)),
    
    # Custom API endpoints
    path('process-ocr/', ProcessOCRView.as_view(), name='process-ocr'),
    path('passport/', ProcessPassportOCRView.as_view(), name='passport'),
    path('uae-visa/', ProcessVisaOCRView.as_view(), name='uae-visa'),
    path('recommendations/', GetProductRecommendationsView.as_view(), name='recommendations'),
    path('create-policy/', CreatePolicyView.as_view(), name='create-policy'),
]
