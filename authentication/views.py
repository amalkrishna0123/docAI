from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from .models import OTP, UserProfile
from .serializers import (
    OTPRequestSerializer,
    OTPVerifySerializer,
    UserSerializer,
    UserProfileSerializer
)
from rest_framework_simplejwt.tokens import RefreshToken


class SendOTPView(APIView):
    """
    Send OTP to user's email for authentication
    POST /api/auth/send-otp/
    Body: {"email": "user@example.com"}
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = OTPRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        email = serializer.validated_data['email']
        
        # Generate OTP
        otp_code = OTP.generate_otp(length=settings.OTP_LENGTH)
        
        # Save OTP to database
        otp_instance = OTP.objects.create(
            email=email,
            otp_code=otp_code
        )
        
        # Send OTP via email
        try:
            subject = 'Your Medical Insurance Portal OTP'
            message = f'''
Hello,

Your OTP for Medical Insurance Portal is: {otp_code}

This OTP is valid for {settings.OTP_EXPIRY_MINUTES} minutes.

Please do not share this OTP with anyone.

Thank you,
Medical Insurance Team
            '''
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
            
            return Response({
                'success': True,
                'message': 'OTP sent successfully to your email',
                'email': email
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            # If email fails, still return success for development
            # But log the error
            print(f"Email sending failed: {str(e)}")
            return Response({
                'success': True,
                'message': 'OTP sent successfully (Console Mode)',
                'email': email,
                'otp': otp_code  # Only in development!
            }, status=status.HTTP_200_OK)


class VerifyOTPView(APIView):
    """
    Verify OTP and login/register user
    POST /api/auth/verify-otp/
    Body: {"email": "user@example.com", "otp_code": "1234"}
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        email = serializer.validated_data['email']
        otp_code = serializer.validated_data['otp_code']
        
        # Find the latest OTP for this email
        try:
            otp_instance = OTP.objects.filter(
                email=email,
                otp_code=otp_code,
                is_verified=False
            ).latest('created_at')
        except OTP.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Invalid OTP'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if OTP is still valid
        if not otp_instance.is_valid():
            return Response({
                'success': False,
                'message': 'OTP has expired. Please request a new one.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Mark OTP as verified
        otp_instance.is_verified = True
        otp_instance.save()
        
        # Get or create user
        user, created = User.objects.get_or_create(
            username=email,
            defaults={'email': email}
        )
        
        # Create user profile if new user
        if created:
            UserProfile.objects.create(user=user)
        
        # Login user
        refresh = RefreshToken.for_user(user)

        return Response({
            'success': True,
            'message': 'Login successful',
            'user': UserSerializer(user).data,
            'access_token': str(refresh.access_token),
            'refresh_token': str(refresh),
            'expires_in_minutes': 60,
            'is_new_user': created
        }, status=status.HTTP_200_OK)



class LogoutView(APIView):
    """
    Logout user
    POST /api/auth/logout/
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        logout(request)
        return Response({
            'success': True,
            'message': 'Logged out successfully'
        }, status=status.HTTP_200_OK)


class CurrentUserView(APIView):
    """
    Get current logged in user
    GET /api/auth/me/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response({
            'success': True,
            'user': serializer.data
        }, status=status.HTTP_200_OK)


class CheckAuthView(APIView):
    """
    Check if user is authenticated
    GET /api/auth/check/
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        if request.user.is_authenticated:
            return Response({
                'authenticated': True,
                'user': UserSerializer(request.user).data
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'authenticated': False
            }, status=status.HTTP_200_OK)
