from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import uuid

from .models import InsuranceApplication, InsurancePolicy, ChatMessage
from .serializers import (
    InsuranceApplicationSerializer,
    InsurancePolicySerializer,
    ChatMessageSerializer,
    OCRDataSerializer,
    PassportOCRDataSerializer,
    VisaOCRDataSerializer,
    ProductRecommendationSerializer
)


class InsuranceApplicationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Insurance Applications
    GET /api/insurance/applications/ - List all applications
    POST /api/insurance/applications/ - Create new application
    GET /api/insurance/applications/{id}/ - Get specific application
    PUT/PATCH /api/insurance/applications/{id}/ - Update application
    DELETE /api/insurance/applications/{id}/ - Delete application
    """
    serializer_class = InsuranceApplicationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return applications for current user only"""
        return InsuranceApplication.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        """Set the user when creating application"""
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get active application for current user"""
        application = InsuranceApplication.objects.filter(
            user=request.user,
            status__in=['Draft', 'In Progress', 'Pending OCR', 'Under Review']
        ).first()
        
        if application:
            serializer = self.get_serializer(application)
            return Response({
                'success': True,
                'application': serializer.data
            })
        else:
            return Response({
                'success': False,
                'message': 'No active application found'
            }, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=False, methods=['post'])
    def reset_session(self, request):
        """
        Clears the current session:
        1. Deletes any 'In Progress'/'Draft' applications for the user.
        2. Deletes all chat history for the user.
        """
        # 1. Delete active applications
        deleted_apps = InsuranceApplication.objects.filter(
            user=request.user, 
            status__in=['Draft', 'In Progress', 'Pending OCR', 'Under Review']
        ).delete()
        
        # 2. Delete all chat messages for this user (or we could scope it to session)
        # The user requested "clear all chats", so we delete all messages for this user.
        ChatMessage.objects.filter(user=request.user).delete()
        
        return Response({
            'success': True, 
            'message': 'Session reset successfully. Chat history and active applications cleared.',
            'details': {
                'apps_deleted': deleted_apps[0],
            }
        })
        
    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """Update application status"""
        application = self.get_object()
        new_status = request.data.get('status')
        
        if new_status not in dict(InsuranceApplication.STATUS_CHOICES):
            return Response({
                'success': False,
                'message': 'Invalid status'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        application.status = new_status
        application.save()
        
        return Response({
            'success': True,
            'message': 'Status updated successfully',
            'application': self.get_serializer(application).data
        })


import logging
from .utils import EmiratesIDExtractor, PassportExtractor, VisaExtractor

logger = logging.getLogger(__name__)

# Max file size (5MB)
MAX_FILE_SIZE = 5 * 1024 * 1024
ALLOWED_CONTENT_TYPES = ['application/pdf', 'image/jpeg', 'image/png']

class ProcessOCRView(APIView):
    """
    Process uploaded Emirates ID and extract data
    POST /api/insurance/process-ocr/
    Body: multipart/form-data with 'document' file (PDF, JPG, PNG)
    Optional: 'employment_type' ('Employee' or 'Dependent')
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            document = request.FILES.get('document')
            application_id = request.data.get('application_id')
            employment_type = request.data.get('employment_type', 'Employee')
            
            # 1. Validation
            if not document:
                return Response({
                    'success': False,
                    'message': 'No document provided'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if document.size > MAX_FILE_SIZE:
                return Response({
                    'success': False,
                    'message': 'File too large. Maximum size is 1MB.'
                }, status=status.HTTP_400_BAD_REQUEST)
                
            # Basic content type check (can be improved with python-magic)
            if document.content_type not in ALLOWED_CONTENT_TYPES:
                # Fallback check on extension if content_type is generic
                ext = document.name.split('.')[-1].lower()
                if ext not in ['pdf', 'jpg', 'jpeg', 'png']:
                    return Response({
                        'success': False,
                        'message': 'Invalid file type. Only PDF, JPG, and PNG are allowed.'
                    }, status=status.HTTP_400_BAD_REQUEST)

            # 2. Save document to application (Optional step, but potential failure point)
            if application_id:
                try:
                    application = InsuranceApplication.objects.get(
                        id=application_id,
                        user=request.user
                    )
                    # Rewind before read/save if needed, though Django handles this mostly
                    application.emirates_id_document = document
                    application.status = 'Pending OCR'
                    application.save()
                    
                    # IMPORTANT: Reset file pointer after save() consumed it
                    if hasattr(document, 'seek'):
                        document.seek(0)
                        
                except InsuranceApplication.DoesNotExist:
                     logger.warning(f"Application {application_id} not found for user {request.user.id}")
                except Exception as e:
                    logger.error(f"Failed to save document to DB: {e}", exc_info=True)
                    # We continue even if save fails? Or abort? 
                    # Let's continue to give the user the extracted data at least.
                    if hasattr(document, 'seek'):
                        document.seek(0)

            # 3. Real OCR Processing
            extractor = EmiratesIDExtractor()
            
            # Ensure file pointer is at start
            if hasattr(document, 'seek'):
                document.seek(0)

            extracted_data = extractor.process_pdf(document, employment_type=employment_type)

            if 'error' in extracted_data:
                 error_msg = extracted_data['error']
                 if isinstance(error_msg, list):
                     error_msg = ", ".join(error_msg)
                 
                 logger.error(f"OCR Extraction Failed: {error_msg}")
                 print(f"DEBUG: OCR Failed - {error_msg}") # Explicit print for user
                 return Response({
                    'success': False,
                    'message': f"OCR Service Failed: {error_msg}"
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

            # 4. Success Response
            final_data = {
                'emirates_id': extracted_data.get('emirates_id', ''),
                'full_name': extracted_data.get('full_name', ''),
                'date_of_birth': extracted_data.get('date_of_birth'),
                'issuing_date': extracted_data.get('issuing_date'),
                'expiry_date': extracted_data.get('expiry_date'),
                'nationality': extracted_data.get('nationality', ''),
                'gender': extracted_data.get('gender', 'Male'), 
                'issuing_place': extracted_data.get('issuing_place', ''), 
                'occupation': extracted_data.get('occupation', ''),
                'sponsor_name': extracted_data.get('sponsor_name', '')
            }
            
            serializer = OCRDataSerializer(data=final_data)
            if serializer.is_valid():
                return Response({
                    'success': True,
                    'message': 'Document processed successfully',
                    'data': serializer.validated_data
                })
            else:
                logger.warning(f"Partial OCR data: {serializer.errors}")
                return Response({
                    'success': True, 
                    'message': 'Partial data extracted. Please map manually.',
                    'data': final_data
                })

        except Exception as e:
            # Catch-all for unexpected crashes (500)
            logger.critical(f"ProcessOCRView Critical Error: {str(e)}", exc_info=True)
            print(f"DEBUG CRITICAL ERROR: {str(e)}") # Explicit print
            return Response({
                'success': False,
                'message': 'An unexpected error occurred while processing your document. Please try again or enter details manually.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProcessPassportOCRView(APIView):
    """
    Process uploaded Passport and extract data
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            document = request.FILES.get('document')
            application_id = request.data.get('application_id')
            
            if not document:
                 return Response({'success': False, 'message': 'No document provided'}, status=400)

            extractor = PassportExtractor()
            extracted_data = extractor.process_passport(document)

            if 'error' in extracted_data:
                 return Response({'success': False, 'message': extracted_data['error']}, status=503)

            # Save to application if provided
            if application_id:
                try:
                    app = InsuranceApplication.objects.get(id=application_id, user=request.user)
                    app.passport_document = document
                    app.passport_number = extracted_data.get('passport_number')
                    app.passport_expiry_date = extracted_data.get('expiry_date')
                    app.save()
                except: pass

            serializer = PassportOCRDataSerializer(data=extracted_data)
            if serializer.is_valid():
                return Response({'success': True, 'data': serializer.validated_data})
            return Response({'success': True, 'data': extracted_data}) # Fallback if partial

        except Exception as e:
            return Response({'success': False, 'message': str(e)}, status=500)


class ProcessVisaOCRView(APIView):
    """
    Process uploaded Visa and extract data
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            document = request.FILES.get('document')
            application_id = request.data.get('application_id')
            
            if not document:
                 return Response({'success': False, 'message': 'No document provided'}, status=400)

            extractor = VisaExtractor()
            extracted_data = extractor.process_visa(document)

            if 'error' in extracted_data:
                 return Response({'success': False, 'message': extracted_data['error']}, status=503)

            # Save to application if provided
            if application_id:
                try:
                    app = InsuranceApplication.objects.get(id=application_id, user=request.user)
                    app.visa_document = document
                    app.visa_number = extracted_data.get('visa_number')
                    app.visa_expiry_date = extracted_data.get('expiry_date')
                    app.save()
                except: pass

            serializer = VisaOCRDataSerializer(data=extracted_data)
            if serializer.is_valid():
                return Response({'success': True, 'data': serializer.validated_data})
            return Response({'success': True, 'data': extracted_data}) # Fallback

        except Exception as e:
            return Response({'success': False, 'message': str(e)}, status=500)


class GetProductRecommendationsView(APIView):
    """
    Get insurance product recommendations based on criteria
    POST /api/insurance/recommendations/
    Body: {"salary_range": "<4000", "issuing_place": "Dubai"}
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        salary_range = request.data.get('salary_range')
        issuing_place = request.data.get('issuing_place', '').lower()
        
        if not salary_range or not issuing_place:
            return Response({
                'success': False,
                'message': 'salary_range and issuing_place are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        products = []
        
        # Product logic as per requirements
        if 'dubai' in issuing_place:
            if salary_range == '<4000':
                products.append({
                    'plan_name': 'DHA Basic',
                    'plan_type': 'LSB',
                    'premium_amount': '864.00',
                    'description': 'Basic medical coverage for low salary bracket',
                    'url': 'https://example.com/dha-basic-lsb'
                })
            elif salary_range in ['4000-5000', '>5000']:
                products.append({
                    'plan_name': 'DHA Basic',
                    'plan_type': 'LSB',
                    'premium_amount': '864.00',
                    'description': 'Basic medical coverage for low salary bracket',
                    'url': 'https://example.com/dha-basic-lsb'
                })
                products.append({
                    'plan_name': 'DHA Basic',
                    'plan_type': 'NLSB',
                    'premium_amount': '1893.00',
                    'description': 'Enhanced medical coverage for non-low salary bracket',
                    'url': 'https://example.com/dha-basic-nlsb'
                })
        
        elif 'abu dhabi' in issuing_place:
            if salary_range == '>5000':
                products.append({
                    'plan_name': 'DHA Basic',
                    'plan_type': 'NLSB',
                    'premium_amount': '1893.00',
                    'description': 'Enhanced medical coverage for non-low salary bracket',
                    'url': 'https://example.com/dha-basic-nlsb'
                })
            # else: No products available for Abu Dhabi low salary
        
        else:
            # Default fallback for other emirates
            products.append({
                'plan_name': 'DHA Basic',
                'plan_type': 'LSB',
                'premium_amount': '864.00',
                'description': 'Basic medical coverage',
                'url': 'https://example.com/dha-basic-lsb'
            })
        
        serializer = ProductRecommendationSerializer(data=products, many=True)
        if serializer.is_valid():
            return Response({
                'success': True,
                'products': serializer.validated_data,
                'count': len(serializer.validated_data)
            })
        else:
            return Response({
                'success': False,
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)


class InsurancePolicyViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Insurance Policies (Read Only)
    GET /api/insurance/policies/ - List all user policies
    GET /api/insurance/policies/{id}/ - Get specific policy
    """
    serializer_class = InsurancePolicySerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return policies for current user only"""
        return InsurancePolicy.objects.filter(
            application__user=self.request.user
        )
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get all active policies for current user"""
        policies = self.get_queryset().filter(status='Active')
        serializer = self.get_serializer(policies, many=True)
        return Response({
            'success': True,
            'policies': serializer.data,
            'count': policies.count()
        })


class CreatePolicyView(APIView):
    """
    Create a policy from completed application
    POST /api/insurance/create-policy/
    Body: {"application_id": 1, "plan_name": "DHA Basic", "plan_type": "LSB", "premium_amount": "864.00"}
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        application_id = request.data.get('application_id')
        plan_name = request.data.get('plan_name')
        plan_type = request.data.get('plan_type')
        premium_amount = request.data.get('premium_amount')
        
        if not all([application_id, plan_name, plan_type, premium_amount]):
            return Response({
                'success': False,
                'message': 'All fields are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get application
        try:
            application = InsuranceApplication.objects.get(
                id=application_id,
                user=request.user
            )
        except InsuranceApplication.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Application not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if application is valid
        if not application.is_emirates_id_valid():
            return Response({
                'success': False,
                'message': 'Emirates ID is expired'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if policy already exists for this application
        if hasattr(application, 'policy'):
            return Response({
                'success': False,
                'message': 'Policy already exists for this application'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if Emirates ID already has an active policy
        existing_policy = InsurancePolicy.objects.filter(
            application__emirates_id=application.emirates_id,
            status='Active'
        ).exists()
        
        if existing_policy:
            return Response({
                'success': False,
                'message': 'This Emirates ID already has an active policy'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Generate policy number
        policy_number = f'POL-{timezone.now().year}-{str(uuid.uuid4())[:8].upper()}'
        
        # Create policy
        policy = InsurancePolicy.objects.create(
            application=application,
            policy_number=policy_number,
            plan_name=plan_name,
            plan_type=plan_type,
            premium_amount=Decimal(premium_amount),
            expiry_date=timezone.now().date() + timedelta(days=365)
        )
        
        # Update application status
        application.status = 'Completed'
        application.save()
        
        serializer = InsurancePolicySerializer(policy)
        return Response({
            'success': True,
            'message': 'Policy created successfully',
            'policy': serializer.data
        }, status=status.HTTP_201_CREATED)


class ChatMessageViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Chat Messages
    GET /api/insurance/chat/ - List chat history
    POST /api/insurance/chat/ - Save new chat message
    """
    serializer_class = ChatMessageSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return chat messages for current user"""
        session_id = self.request.query_params.get('session_id')
        queryset = ChatMessage.objects.filter(user=self.request.user)
        
        if session_id:
            queryset = queryset.filter(session_id=session_id)
        
        return queryset
    
    def perform_create(self, serializer):
        """Set the user when creating message"""
        serializer.save(user=self.request.user)
