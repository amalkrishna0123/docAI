from django.db import models
from django.contrib.auth.models import User
from django.core.validators import FileExtensionValidator


class InsuranceApplication(models.Model):
    """Main insurance application model"""
    
    TYPE_CHOICES = [
        ('Employee', 'Employee'),
        ('Dependent', 'Dependent'),
    ]
    
    DEPENDENT_TYPE_CHOICES = [
        ('Spouse', 'Spouse'),
        ('Child', 'Child'),
        ('', 'N/A'),
    ]
    
    SALARY_CHOICES = [
        ('<4000', 'Below 4000 AED'),
        ('4000-5000', '4000-5000 AED'),
        ('>5000', 'Above 5000 AED'),
    ]
    
    GENDER_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),
    ]
    
    STATUS_CHOICES = [
        ('Draft', 'Draft'),
        ('In Progress', 'In Progress'),
        ('Pending OCR', 'Pending OCR'),
        ('Under Review', 'Under Review'),
        ('Completed', 'Completed'),
        ('Rejected', 'Rejected'),
    ]
    
    # User and Basic Info
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='insurance_applications')
    language = models.CharField(max_length=10, choices=[
        ('en', 'English'),
        ('ml', 'Malayalam'),
        ('ar', 'Arabic'),
        ('hi', 'Hindi'),
    ])
    
    # Application Type
    application_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    dependent_type = models.CharField(max_length=20, choices=DEPENDENT_TYPE_CHOICES, blank=True, null=True)
    salary_range = models.CharField(max_length=20, choices=SALARY_CHOICES, blank=True, null=True)
    
    # Emirates ID Data
    emirates_id = models.CharField(max_length=50, unique=True)
    full_name = models.CharField(max_length=200)
    date_of_birth = models.DateField(null=True, blank=True)
    issuing_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField()
    nationality = models.CharField(max_length=100)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    issuing_place = models.CharField(max_length=100)
    occupation = models.CharField(max_length=200, blank=True, null=True)
    sponsor_name = models.CharField(max_length=200, blank=True, null=True)

    VISA_TYPE_CHOICES = [
        ('NEW', 'New Entrant'),
        ('TRANSFER', 'Transferred from Other Emirates'),
        ('EXISTING_AD', 'Existing Abu Dhabi Visa Holder'),
        ('NEWBORN', 'Newborn'),
    ]
    
    # Contact
    mobile_number = models.CharField(max_length=15)

    uid_number = models.CharField(
        max_length=50,
        blank=False,
        null=False
    )

    visa_type = models.CharField(
        max_length=20,
        choices=VISA_TYPE_CHOICES,
        blank=True,
        null=True
    )

    visa_status_date = models.DateField(
        null=True, 
        blank=True,
        help_text="Entry Date, Last Expiry Date, or Date of Birth based on Visa Type"
    )

    
    # Documents
    emirates_id_document = models.FileField(
        upload_to='emirates_ids/',
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png'])],
        null=True,
        blank=True
    )
    passport_document = models.FileField(
        upload_to='passports/',
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png'])],
        null=True,
        blank=True
    )
    visa_document = models.FileField(
        upload_to='visas/',
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png'])],
        null=True,
        blank=True
    )
    
    # Passport Data
    passport_number = models.CharField(max_length=50, blank=True, null=True)
    passport_expiry_date = models.DateField(null=True, blank=True)
    passport_name = models.CharField(max_length=200, blank=True, null=True)
    passport_dob = models.DateField(null=True, blank=True)
    passport_nationality = models.CharField(max_length=100, blank=True, null=True)
    
    # Visa Data
    visa_number = models.CharField(max_length=50, blank=True, null=True)
    visa_expiry_date = models.DateField(null=True, blank=True)
    visa_full_name = models.CharField(max_length=200, blank=True, null=True)
    visa_eid_number = models.CharField(max_length=50, blank=True, null=True)
    visa_passport_number = models.CharField(max_length=50, blank=True, null=True)

    # Medical Questionnaire (MAF)
    has_medical_conditions = models.BooleanField(null=True, blank=True)
    maf_responses = models.JSONField(default=dict, blank=True) # Stores responses to 9 questions
    
    # Status and Timestamps
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Draft')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Chat History (JSON field to store conversation)
    chat_history = models.JSONField(default=list, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.full_name} - {self.emirates_id} ({self.status})"
    
    def is_emirates_id_valid(self):
        """Check if Emirates ID is not expired"""
        from django.utils import timezone
        return self.expiry_date > timezone.now().date()


class InsurancePolicy(models.Model):
    """Insurance policy after application completion"""
    
    PLAN_TYPE_CHOICES = [
        ('LSB', 'Low Salary Bracket'),
        ('NLSB', 'Non-Low Salary Bracket'),
    ]
    
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Expired', 'Expired'),
        ('Cancelled', 'Cancelled'),
    ]
    
    # Link to application
    application = models.OneToOneField(
        InsuranceApplication,
        on_delete=models.CASCADE,
        related_name='policy'
    )
    
    # Policy Details
    policy_number = models.CharField(max_length=50, unique=True)
    plan_name = models.CharField(max_length=100)
    plan_type = models.CharField(max_length=10, choices=PLAN_TYPE_CHOICES)
    premium_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Policy Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Active')
    issue_date = models.DateField(auto_now_add=True)
    expiry_date = models.DateField()
    
    # UAE Rule: Only one policy per Emirates ID
    # This is enforced at the application level
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Insurance Policies'
    
    def __str__(self):
        return f"{self.policy_number} - {self.plan_name} ({self.status})"


class ChatMessage(models.Model):
    """Store chat messages for AI Assistant"""
    
    MESSAGE_TYPE_CHOICES = [
        ('user', 'User'),
        ('bot', 'Bot'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_messages')
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPE_CHOICES)
    content = models.TextField()
    session_id = models.CharField(max_length=100, db_index=True)  # To group conversations
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.message_type} - {self.created_at}"
