from django.db import models


class UAEDocumentVisa(models.Model):
    """
    Lightweight OCR storage model for testing UAE visa extraction.
    This model is intentionally decoupled from users, chat, and insurance.
    """

    emirates_id = models.CharField(max_length=50, blank=True, null=True)
    permit_number = models.CharField(max_length=50, blank=True, null=True)
    file_number = models.CharField(max_length=50, blank=True, null=True)
    uid_no = models.CharField(max_length=50, blank=True, null=True)
    passport_no = models.CharField(max_length=50, blank=True, null=True)
    name = models.CharField(max_length=200, blank=True, null=True)
    nationality = models.CharField(max_length=100, blank=True, null=True)
    profession = models.CharField(max_length=200, blank=True, null=True)

    issuing_date = models.CharField(max_length=50, blank=True, null=True)
    expiry_date = models.CharField(max_length=50, blank=True, null=True)
    sponsor_name = models.CharField(max_length=200, blank=True, null=True)
    employer = models.CharField(max_length=200, blank=True, null=True)
    stamp_date = models.CharField(max_length=50, blank=True, null=True)

    # Travel / Transaction fields
    from_date = models.CharField(max_length=50, blank=True, null=True)
    to_date = models.CharField(max_length=50, blank=True, null=True)
    transaction_date = models.CharField(max_length=50, blank=True, null=True)
    transaction_type = models.CharField(max_length=100, blank=True, null=True)
    port_name = models.CharField(max_length=200, blank=True, null=True)

    raw_text = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"UAE Visa ({self.file_number or 'N/A'})"


class UAEDocumentPassport(models.Model):
    """Model for UAE Passport OCR data"""
    passport_number = models.CharField(max_length=50, blank=True, null=True)
    full_name = models.CharField(max_length=200, blank=True, null=True)
    nationality = models.CharField(max_length=100, blank=True, null=True)
    date_of_birth = models.CharField(max_length=50, blank=True, null=True)
    expiry_date = models.CharField(max_length=50, blank=True, null=True)
    stamp_date = models.CharField(max_length=50, blank=True, null=True)

    # Travel / Transaction fields
    from_date = models.CharField(max_length=50, blank=True, null=True)
    to_date = models.CharField(max_length=50, blank=True, null=True)
    transaction_date = models.CharField(max_length=50, blank=True, null=True)
    transaction_type = models.CharField(max_length=100, blank=True, null=True)
    port_name = models.CharField(max_length=200, blank=True, null=True)
    
    raw_text = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Passport ({self.passport_number or 'N/A'})"

class UAEDocumentEmiratesID(models.Model):
    """Model for UAE Emirates ID OCR data"""
    emirates_id = models.CharField(max_length=50, blank=True, null=True)
    name = models.CharField(max_length=200, blank=True, null=True)
    nationality = models.CharField(max_length=100, blank=True, null=True)
    dob = models.CharField(max_length=50, blank=True, null=True)
    expiry_date = models.CharField(max_length=50, blank=True, null=True)
    issuing_date = models.CharField(max_length=50, blank=True, null=True)
    family_sponsor_name = models.CharField(max_length=200, blank=True, null=True)
    card_type = models.CharField(max_length=50, blank=True, null=True)
    
    raw_text = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Emirates ID ({self.emirates_id or 'N/A'})"

class UAELabourContract(models.Model):
    """Model for UAE Labour Contract OCR data (MOHRE)"""
    # Employer / Company Details
    establishment_name = models.CharField(max_length=200, blank=True, null=True)
    establishment_number = models.CharField(max_length=100, blank=True, null=True)
    employer_representative = models.CharField(max_length=200, blank=True, null=True)
    emirate = models.CharField(max_length=100, blank=True, null=True)
    employer_email = models.CharField(max_length=200, blank=True, null=True)
    employer_phone = models.CharField(max_length=100, blank=True, null=True)

    # Contract Metadata
    work_style = models.CharField(max_length=100, blank=True, null=True)
    transaction_number = models.CharField(max_length=100, blank=True, null=True)
    contract_type = models.CharField(max_length=100, blank=True, null=True)
    contract_issue_date = models.CharField(max_length=100, blank=True, null=True)

    # Employee Details
    employee_name = models.CharField(max_length=200, blank=True, null=True)
    employee_nationality = models.CharField(max_length=100, blank=True, null=True)
    employee_dob = models.CharField(max_length=100, blank=True, null=True)
    employee_passport_no = models.CharField(max_length=100, blank=True, null=True)
    employee_qualification = models.CharField(max_length=200, blank=True, null=True)
    employee_phone = models.CharField(max_length=100, blank=True, null=True)

    # Job Information
    job_title = models.CharField(max_length=200, blank=True, null=True)
    work_hours = models.CharField(max_length=100, blank=True, null=True)
    weekly_rest = models.CharField(max_length=100, blank=True, null=True)
    annual_leave = models.CharField(max_length=100, blank=True, null=True)

    # Contract Period
    contract_start_date = models.CharField(max_length=50, blank=True, null=True)
    contract_end_date = models.CharField(max_length=50, blank=True, null=True)

    # Ministry Approval
    approval_date = models.CharField(max_length=50, blank=True, null=True)

    # Salary Information
    total_salary = models.CharField(max_length=100, blank=True, null=True)

    raw_text = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Labour Contract ({self.establishment_number or 'N/A'})"


class UAEMedicalApplicationForm(models.Model):
    """Medical Application Form (MAF) extraction"""

    # Applicant Info
    insured_name = models.CharField(max_length=200, blank=True, null=True)
    application_date = models.CharField(max_length=50, blank=True, null=True)
    required_plan = models.CharField(max_length=100, blank=True, null=True)
    application_policy_no = models.CharField(max_length=100, blank=True, null=True)
    current_address = models.CharField(max_length=300, blank=True, null=True)
    active_at_work_since = models.CharField(max_length=50, blank=True, null=True)

    # Personal Details
    nationality = models.CharField(max_length=100, blank=True, null=True)
    gender = models.CharField(max_length=20, blank=True, null=True)
    date_of_birth = models.CharField(max_length=50, blank=True, null=True)
    marital_status = models.CharField(max_length=50, blank=True, null=True)

    height_cm = models.CharField(max_length=20, blank=True, null=True)
    weight_kg = models.CharField(max_length=20, blank=True, null=True)

    uae_resident = models.CharField(max_length=10, blank=True, null=True)
    already_insured = models.CharField(max_length=10, blank=True, null=True)
    insured_since = models.CharField(max_length=50, blank=True, null=True)

    # Insurance History
    insurance_substandard_terms = models.CharField(max_length=10, blank=True, null=True)
    insurance_declined = models.CharField(max_length=10, blank=True, null=True)
    hazardous_sports = models.CharField(max_length=10, blank=True, null=True)
    hazardous_sports_details = models.TextField(blank=True, null=True)

    # Medical Questions
    infectious_diseases = models.CharField(max_length=10, blank=True, null=True)
    cancer = models.CharField(max_length=10, blank=True, null=True)
    endocrine_diseases = models.CharField(max_length=10, blank=True, null=True)
    blood_disorders = models.CharField(max_length=10, blank=True, null=True)
    mental_disorders = models.CharField(max_length=10, blank=True, null=True)
    nervous_system = models.CharField(max_length=10, blank=True, null=True)
    cardiovascular = models.CharField(max_length=10, blank=True, null=True)
    respiratory = models.CharField(max_length=10, blank=True, null=True)
    digestive_system = models.CharField(max_length=10, blank=True, null=True)
    genitourinary = models.CharField(max_length=10, blank=True, null=True)
    maternity_history = models.CharField(max_length=10, blank=True, null=True)
    musculoskeletal = models.CharField(max_length=10, blank=True, null=True)
    congenital = models.CharField(max_length=10, blank=True, null=True)
    perinatal = models.CharField(max_length=10, blank=True, null=True)
    injury_poisoning = models.CharField(max_length=10, blank=True, null=True)
    previous_hospitalization = models.CharField(max_length=10, blank=True, null=True)
    chronic_disease = models.CharField(max_length=10, blank=True, null=True)
    pre_existing_disease = models.CharField(max_length=10, blank=True, null=True)
    organ_surgery = models.CharField(max_length=10, blank=True, null=True)
    good_health = models.CharField(max_length=10, blank=True, null=True)
    weight_change = models.CharField(max_length=10, blank=True, null=True)
    smoking_alcohol = models.CharField(max_length=10, blank=True, null=True)
    bone_fractures = models.CharField(max_length=10, blank=True, null=True)
    Shortness_vision = models.CharField(max_length=10, blank=True, null=True)
    Hepatitis = models.CharField(max_length=10, blank=True, null=True)

    # Dental
    dental_problems = models.CharField(max_length=10, blank=True, null=True)
    dental_details = models.TextField(blank=True, null=True)
    dental_last_treatment = models.CharField(max_length=50, blank=True, null=True)

    # Pregnancy
    pregnant = models.CharField(max_length=10, blank=True, null=True)
    pregnancy_complications = models.CharField(max_length=10, blank=True, null=True)
    last_menstrual_period = models.CharField(max_length=50, blank=True, null=True)
    trying_to_conceive = models.CharField(max_length=10, blank=True, null=True)
    fertility_treatment = models.CharField(max_length=10, blank=True, null=True)

    # Cancer Section
    has_cancer = models.CharField(max_length=10, blank=True, null=True)
    cancer_status = models.CharField(max_length=50, blank=True, null=True)
    cancer_diagnosis = models.TextField(blank=True, null=True)
    cancer_surgery = models.TextField(blank=True, null=True)
    cancer_chemotherapy_cycles = models.TextField(blank=True, null=True)
    cancer_radiotherapy_cycles = models.TextField(blank=True, null=True)
    cancer_radiation_cycles = models.TextField(blank=True, null=True)
    cancer_medication = models.TextField(blank=True, null=True)
    family_cancer_history = models.CharField(max_length=10, blank=True, null=True)

    raw_text = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"MAF ({self.insured_name or 'Unknown'})"


class UAEDocumentCOC(models.Model):
    """Model for Continuity Certificate (COC) OCR data"""
    insured_name = models.CharField(max_length=200, blank=True, null=True)
    policy_holder_name = models.CharField(max_length=200, blank=True, null=True)
    policy_number = models.CharField(max_length=100, blank=True, null=True)
    policy_expiry_date = models.CharField(max_length=50, blank=True, null=True)
    inception_date = models.CharField(max_length=50, blank=True, null=True)
    insured_until = models.CharField(max_length=50, blank=True, null=True)
    coc_reference_no = models.CharField(max_length=100, blank=True, null=True)
    coc_validity_date = models.CharField(max_length=50, blank=True, null=True)
    issue_date = models.CharField(max_length=50, blank=True, null=True)
    insurer_name = models.CharField(max_length=200, blank=True, null=True)
    gender = models.CharField(max_length=20, blank=True, null=True)
    date_of_birth = models.CharField(max_length=50, blank=True, null=True)

    raw_text = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"COC ({self.coc_reference_no or 'N/A'})"


class UAEDocumentResidenceCancellation(models.Model):
    """Model for Residence Cancellation OCR data"""
    uid_no = models.CharField(max_length=50, blank=True, null=True)
    emirates_id = models.CharField(max_length=50, blank=True, null=True)
    residence_no = models.CharField(max_length=100, blank=True, null=True)
    passport_no = models.CharField(max_length=50, blank=True, null=True)
    full_name = models.CharField(max_length=200, blank=True, null=True)
    profession = models.CharField(max_length=200, blank=True, null=True)
    employer = models.CharField(max_length=200, blank=True, null=True)
    place_of_issue = models.CharField(max_length=200, blank=True, null=True)
    cancel_date = models.CharField(max_length=50, blank=True, null=True)

    raw_text = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Residence Cancellation ({self.residence_no or 'N/A'})"


class UAEDocumentTravelHistory(models.Model):
    """Model for Travel History / Transaction logs OCR data"""
    passport_no = models.CharField(max_length=50, blank=True, null=True)
    name = models.CharField(max_length=200, blank=True, null=True)
    from_date = models.CharField(max_length=50, blank=True, null=True)
    to_date = models.CharField(max_length=50, blank=True, null=True)
    transaction_date = models.CharField(max_length=50, blank=True, null=True)
    transaction_type = models.CharField(max_length=100, blank=True, null=True)
    port_name = models.CharField(max_length=200, blank=True, null=True)

    raw_text = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Travel History ({self.passport_no or 'N/A'})"


class UAEDocumentBusinessLicence(models.Model):
    """Model for Business Licence OCR data"""
    licence_number = models.CharField(max_length=100, blank=True, null=True)
    registry_number = models.CharField(max_length=100, blank=True, null=True)
    unified_registration_number = models.CharField(max_length=100, blank=True, null=True)
    customs_registration_number = models.CharField(max_length=100, blank=True, null=True)

    trade_name = models.CharField(max_length=200, blank=True, null=True)
    legal_form = models.CharField(max_length=200, blank=True, null=True)
    licence_type = models.CharField(max_length=100, blank=True, null=True)
    licence_category = models.CharField(max_length=100, blank=True, null=True)

    establishment_date = models.CharField(max_length=50, blank=True, null=True)
    issuance_date = models.CharField(max_length=50, blank=True, null=True)
    expiry_date = models.CharField(max_length=50, blank=True, null=True)

    paid_up_capital = models.CharField(max_length=100, blank=True, null=True)
    paid_up_capital_in_words = models.TextField(blank=True, null=True)

    adcci_number = models.CharField(max_length=100, blank=True, null=True)
    mohre_establishment_number = models.CharField(max_length=100, blank=True, null=True)
    icp_establishment_number = models.CharField(max_length=100, blank=True, null=True)

    owner_name = models.CharField(max_length=200, blank=True, null=True)
    owner_nationality = models.CharField(max_length=100, blank=True, null=True)
    owner_role = models.CharField(max_length=100, blank=True, null=True)
    share_percentage = models.CharField(max_length=50, blank=True, null=True)

    official_email = models.CharField(max_length=200, blank=True, null=True)
    official_mobile = models.CharField(max_length=100, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    activity_name = models.TextField(blank=True, null=True)
    activity_code = models.TextField(blank=True, null=True)

    raw_text = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Business Licence ({self.licence_number or 'N/A'})"

