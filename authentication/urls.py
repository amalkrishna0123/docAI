from django.urls import path
from .views import (
    SendOTPView,
    VerifyOTPView,
    LogoutView,
    CurrentUserView,
    CheckAuthView
)

app_name = 'authentication'

urlpatterns = [
    path('send-otp/', SendOTPView.as_view(), name='send-otp'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('me/', CurrentUserView.as_view(), name='current-user'),
    path('check/', CheckAuthView.as_view(), name='check-auth'),
]
