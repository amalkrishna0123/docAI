from datetime import datetime
import json
from django.http import JsonResponse
from django.conf import settings
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from .google_document_ai import google_document_ai_ocr
from .models import (
    UAEDocumentPassport, UAEDocumentEmiratesID, UAEDocumentVisa, 
    UAELabourContract, UAEMedicalApplicationForm, UAEDocumentCOC, 
    UAEDocumentResidenceCancellation, UAEDocumentTravelHistory,
    UAEDocumentBusinessLicence, UAEDocumentTOB
)
from .ai_extractor import build_extraction_prompt, call_gemini_ai


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def upload_document(request):
    """
    Universal document upload endpoint.
    Workflow:
      1. Receive any document (image or PDF).
      2. Extract raw text via Google Document AI OCR.
      3. Send OCR text to Gemini with a structured prompt.
      4. AI auto-detects the document type and extracts required fields.
      5. Save to the correct Django model.
      6. Return clean JSON.
    """
    def log_timing(message):
        log_file = settings.BASE_DIR / "extraction_performance.log"
        with open(log_file, "a") as f:
            f.write(f"[{datetime.now()}] {message}\n")
        print(message)

    print("--- [UPLOAD] Universal document upload request received ---")
    try:
        log_timing("Request started")
        # ── Step 1: Read uploaded file ──────────────────────────────────────
        uploaded = request.FILES.get("document") or request.FILES.get("file")
        if not uploaded:
            return JsonResponse({"success": False, "error": "No file uploaded"}, status=400)

        file_bytes = uploaded.read()
        mime_type = (
            "application/pdf"
            if uploaded.name.lower().endswith(".pdf")
            else "image/jpeg"
        )
        log_timing(f"File received: {uploaded.name} ({mime_type})")

        # ── Step 2: Google Document AI OCR ─────────────────────────────────
        start_ocr = datetime.now()
        log_timing("Sending to Google Document AI...")
        doc_result = google_document_ai_ocr(file_bytes, mime_type)
        raw_text = doc_result.text if doc_result else ""
        end_ocr = datetime.now()
        ocr_duration = (end_ocr - start_ocr).total_seconds()
        log_timing(f"OCR finished in {ocr_duration:.2f}s. Text length: {len(raw_text or '')} chars")

        if not raw_text or len(raw_text.strip()) < 10:
            return JsonResponse(
                {"success": False, "error": "OCR returned empty text — check document quality"},
                status=422,
            )

        # ── Step 3: Build prompt & call Gemini AI ─────────────────────
        log_timing("Building AI extraction prompt...")
        requested_doc_type = request.headers.get("X-Selected-Doc-Type", "")
        prompt = build_extraction_prompt(raw_text, requested_doc_type=requested_doc_type)

        start_ai = datetime.now()
        log_timing("Calling Gemini AI...")
        ai_result = call_gemini_ai(prompt, file_bytes=file_bytes, mime_type=mime_type)
        end_ai = datetime.now()
        ai_duration = (end_ai - start_ai).total_seconds()
        log_timing(f"Gemini AI finished in {ai_duration:.2f}s")

        if "error" in ai_result:
            return JsonResponse(
                {"success": False, "error": ai_result["error"]},
                status=502,
            )

        document_type = ai_result.get("document_type", "").strip()
        fields = ai_result.get("data", {})
        print(f"--- [UPLOAD] AI detected document type: {document_type} ---")
        print(f"--- [UPLOAD] Extracted fields: {fields} ---")

        is_tob_context = (requested_doc_type == "TOB" or document_type == "TOB")

        if is_tob_context:
            doc_type_stored = "TOB" if document_type == "TOB" else "Unknown"
            keywords = fields.get("matched_keywords", [])
            sig_pages = fields.get("signature_pages", [])
            sig_locs = fields.get("signature_locations", [])
            
            record = UAEDocumentTOB.objects.create(
                document_type=doc_type_stored,
                matched_keywords=json.dumps(keywords) if isinstance(keywords, list) else str(keywords),
                signature_present=fields.get("signature_present", False),
                signature_pages=json.dumps(sig_pages) if isinstance(sig_pages, list) else str(sig_pages),
                signature_locations=json.dumps(sig_locs) if isinstance(sig_locs, list) else str(sig_locs),
                signature_status=fields.get("signature_status", "declined"),
                validation_status=fields.get("validation_status", "declined"),
                decline_reason=fields.get("decline_reason", "Document is not a TOB" if doc_type_stored == "Unknown" else ""),
                raw_text=raw_text
            )
            print(f"--- [UPLOAD] Saved TOB record ID: {record.id} ---")
            
            response_data = {
                "document_type": doc_type_stored,
                "matched_keywords": keywords,
                "signature_present": fields.get("signature_present", False),
                "signature_pages": sig_pages,
                "signature_locations": sig_locs,
                "signature_status": fields.get("signature_status", "declined"),
                "validation_status": fields.get("validation_status", "declined"),
                "decline_reason": fields.get("decline_reason", "Document is not a TOB" if doc_type_stored == "Unknown" else "")
            }
            return JsonResponse(response_data, status=200)

        # ── Step 4: Save to the correct model ──────────────────────────────
        record_id = None

        if document_type == "Passport":
            record = UAEDocumentPassport.objects.create(
                passport_number=fields.get("passport_number"),
                full_name=fields.get("full_name"),
                nationality=fields.get("nationality"),
                date_of_birth=fields.get("date_of_birth"),
                expiry_date=fields.get("expiry_date"),
                stamp_date=fields.get("stamp_date"),
                from_date=fields.get("from_date"),
                to_date=fields.get("to_date"),
                transaction_date=fields.get("transaction_date"),
                transaction_type=fields.get("transaction_type"),
                port_name=fields.get("port_name"),
                raw_text=raw_text,
            )
            record_id = record.id
            print(f"--- [UPLOAD] Saved Passport record ID: {record_id} ---")

        elif document_type == "Emirates ID":
            record = UAEDocumentEmiratesID.objects.create(
                emirates_id=fields.get("emirates_id"),
                name=fields.get("name"),
                nationality=fields.get("nationality"),
                dob=fields.get("dob"),
                expiry_date=fields.get("expiry_date"),
                issuing_date=fields.get("issuing_date"),
                family_sponsor_name=fields.get("family_sponsor_name"),
                card_type=fields.get("card_type"),
                raw_text=raw_text,
            )
            record_id = record.id
            print(f"--- [UPLOAD] Saved Emirates ID record ID: {record_id} ---")

        elif document_type in ["UAE Visa", "eVisa", "Residence Visa"]:
            record = UAEDocumentVisa.objects.create(
                emirates_id=fields.get("emirates_id"),
                permit_number=fields.get("permit_number"),
                file_number=fields.get("file_number"),
                uid_no=fields.get("uid_no"),
                passport_no=fields.get("passport_no"),
                name=fields.get("name"),
                nationality=fields.get("nationality"),
                profession=fields.get("profession"),
                issuing_date=fields.get("issuing_date"),
                expiry_date=fields.get("expiry_date"),
                sponsor_name=fields.get("sponsor_name"),
                employer=fields.get("employer"),
                stamp_date=fields.get("stamp_date"),
                from_date=fields.get("from_date"),
                to_date=fields.get("to_date"),
                transaction_date=fields.get("transaction_date"),
                transaction_type=fields.get("transaction_type"),
                port_name=fields.get("port_name"),
                raw_text=raw_text,
            )
            record_id = record.id
            print(f"--- [UPLOAD] Saved {document_type} record ID: {record_id} ---")

        elif document_type == "Labour Contract":
            record = UAELabourContract.objects.create(
                establishment_name=fields.get("establishment_name"),
                establishment_number=fields.get("establishment_number"),
                employer_representative=fields.get("employer_representative"),
                emirate=fields.get("emirate"),
                employer_email=fields.get("employer_email"),
                employer_phone=fields.get("employer_phone"),
                work_style=fields.get("work_style"),
                transaction_number=fields.get("transaction_number"),
                contract_type=fields.get("contract_type"),
                contract_issue_date=fields.get("contract_issue_date"),
                employee_name=fields.get("employee_name"),
                employee_nationality=fields.get("employee_nationality"),
                employee_dob=fields.get("employee_dob"),
                employee_passport_no=fields.get("employee_passport_no"),
                employee_qualification=fields.get("employee_qualification"),
                employee_phone=fields.get("employee_phone"),
                job_title=fields.get("job_title"),
                work_hours=fields.get("work_hours"),
                weekly_rest=fields.get("weekly_rest"),
                annual_leave=fields.get("annual_leave"),
                contract_start_date=fields.get("contract_start_date"),
                contract_end_date=fields.get("contract_end_date"),
                approval_date=fields.get("approval_date"),
                total_salary=fields.get("total_salary"),
                raw_text=raw_text,
            )
            record_id = record.id
            print(f"--- [UPLOAD] Saved Labour Contract record ID: {record_id} ---")

        elif document_type == "Medical Application Form":
            record = UAEMedicalApplicationForm.objects.create(
                insured_name=fields.get("insured_name"),
                application_date=fields.get("application_date"),
                required_plan=fields.get("required_plan"),
                application_policy_no=fields.get("application_policy_no"),
                current_address=fields.get("current_address"),
                active_at_work_since=fields.get("active_at_work_since"),
                nationality=fields.get("nationality"),
                gender=fields.get("gender"),
                date_of_birth=fields.get("date_of_birth"),
                marital_status=fields.get("marital_status"),
                height_cm=fields.get("height_cm"),
                weight_kg=fields.get("weight_kg"),
                uae_resident=fields.get("uae_resident"),
                already_insured=fields.get("already_insured"),
                insured_since=fields.get("insured_since"),
                insurance_substandard_terms=fields.get("insurance_substandard_terms"),
                insurance_declined=fields.get("insurance_declined"),
                hazardous_sports=fields.get("hazardous_sports"),
                hazardous_sports_details=fields.get("hazardous_sports_details"),
                infectious_diseases=fields.get("infectious_diseases"),
                cancer=fields.get("cancer"),
                endocrine_diseases=fields.get("endocrine_diseases"),
                blood_disorders=fields.get("blood_disorders"),
                mental_disorders=fields.get("mental_disorders"),
                nervous_system=fields.get("nervous_system"),
                cardiovascular=fields.get("cardiovascular"),
                respiratory=fields.get("respiratory"),
                digestive_system=fields.get("digestive_system"),
                genitourinary=fields.get("genitourinary"),
                maternity_history=fields.get("maternity_history"),
                musculoskeletal=fields.get("musculoskeletal"),
                congenital=fields.get("congenital"),
                perinatal=fields.get("perinatal"),
                injury_poisoning=fields.get("injury_poisoning"),
                previous_hospitalization=fields.get("previous_hospitalization"),
                chronic_disease=fields.get("chronic_disease"),
                pre_existing_disease=fields.get("pre_existing_disease"),
                organ_surgery=fields.get("organ_surgery"),
                good_health=fields.get("good_health"),
                weight_change=fields.get("weight_change"),
                smoking_alcohol=fields.get("smoking_alcohol"),
                bone_fractures=fields.get("bone_fractures"),
                Shortness_vision=fields.get("Shortness_vision"),
                Hepatitis=fields.get("Hepatitis"),
                dental_problems=fields.get("dental_problems"),
                dental_details=fields.get("dental_details"),
                dental_last_treatment=fields.get("dental_last_treatment"),
                pregnant=fields.get("pregnant"),
                pregnancy_complications=fields.get("pregnancy_complications"),
                last_menstrual_period=fields.get("last_menstrual_period"),
                trying_to_conceive=fields.get("trying_to_conceive"),
                fertility_treatment=fields.get("fertility_treatment"),
                has_cancer=fields.get("has_cancer"),
                cancer_status=fields.get("cancer_status"),
                cancer_diagnosis=fields.get("cancer_diagnosis"),
                cancer_surgery=fields.get("cancer_surgery"),
                cancer_chemotherapy_cycles=fields.get("cancer_chemotherapy_cycles"),
                cancer_radiotherapy_cycles=fields.get("cancer_radiotherapy_cycles"),
                cancer_radiation_cycles=fields.get("cancer_radiation_cycles"),
                cancer_medication=fields.get("cancer_medication"),
                family_cancer_history=fields.get("family_cancer_history"),
                raw_text=raw_text,
            )
            record_id = record.id
            print(f"--- [UPLOAD] Saved Medical Application Form record ID: {record_id} ---")

        elif document_type == "COC":
            record = UAEDocumentCOC.objects.create(
                insured_name=fields.get("insured_name"),
                policy_holder_name=fields.get("policy_holder_name"),
                policy_number=fields.get("policy_number"),
                policy_expiry_date=fields.get("policy_expiry_date"),
                inception_date=fields.get("inception_date"),
                insured_until=fields.get("insured_until"),
                coc_reference_no=fields.get("coc_reference_no"),
                coc_validity_date=fields.get("coc_validity_date"),
                issue_date=fields.get("issue_date"),
                insurer_name=fields.get("insurer_name"),
                gender=fields.get("gender"),
                date_of_birth=fields.get("date_of_birth"),
                raw_text=raw_text,
            )
            record_id = record.id
            print(f"--- [UPLOAD] Saved COC record ID: {record_id} ---")

        elif document_type == "Residence Cancellation":
            record = UAEDocumentResidenceCancellation.objects.create(
                uid_no=fields.get("uid_no"),
                emirates_id=fields.get("emirates_id"),
                residence_no=fields.get("residence_no"),
                passport_no=fields.get("passport_no"),
                full_name=fields.get("full_name"),
                profession=fields.get("profession"),
                employer=fields.get("employer"),
                place_of_issue=fields.get("place_of_issue"),
                cancel_date=fields.get("cancel_date"),
                raw_text=raw_text,
            )
            record_id = record.id
            print(f"--- [UPLOAD] Saved Residence Cancellation record ID: {record_id} ---")

        elif document_type == "Travel History":
            record = UAEDocumentTravelHistory.objects.create(
                passport_no=fields.get("passport_no"),
                name=fields.get("name"),
                from_date=fields.get("from_date"),
                to_date=fields.get("to_date"),
                transaction_date=fields.get("transaction_date"),
                transaction_type=fields.get("transaction_type"),
                port_name=fields.get("port_name"),
                raw_text=raw_text,
            )
            record_id = record.id
            print(f"--- [UPLOAD] Saved Travel History record ID: {record_id} ---")

        elif document_type == "Business Licence":
            record = UAEDocumentBusinessLicence.objects.create(
                licence_number=fields.get("licence_number"),
                registry_number=fields.get("registry_number"),
                unified_registration_number=fields.get("unified_registration_number"),
                customs_registration_number=fields.get("customs_registration_number"),
                trade_name=fields.get("trade_name"),
                legal_form=fields.get("legal_form"),
                licence_type=fields.get("licence_type"),
                licence_category=fields.get("licence_category"),
                establishment_date=fields.get("establishment_date"),
                issuance_date=fields.get("issuance_date"),
                expiry_date=fields.get("expiry_date"),
                paid_up_capital=fields.get("paid_up_capital"),
                paid_up_capital_in_words=fields.get("paid_up_capital_in_words"),
                adcci_number=fields.get("adcci_number"),
                mohre_establishment_number=fields.get("mohre_establishment_number"),
                icp_establishment_number=fields.get("icp_establishment_number"),
                owner_name=fields.get("owner_name"),
                owner_nationality=fields.get("owner_nationality"),
                owner_role=fields.get("owner_role"),
                share_percentage=fields.get("share_percentage"),
                official_email=fields.get("official_email"),
                official_mobile=fields.get("official_mobile"),
                address=fields.get("address"),
                activity_name=fields.get("activity_name"),
                activity_code=fields.get("activity_code"),
                raw_text=raw_text,
            )
            record_id = record.id
            print(f"--- [UPLOAD] Saved Business Licence record ID: {record_id} ---")

        else:
            print(f"--- [UPLOAD] WARNING: Unknown document type returned by AI: '{document_type}' ---")
            print(f"--- [UPLOAD] Full AI result: {ai_result} ---")
            return JsonResponse(
                {
                    "success": False,
                    "error": f"AI could not identify document type. Got: '{document_type}'",
                    "raw_ai_response": ai_result,
                },
                status=422,
            )

        # ── Step 5: Return clean response ───────────────────────────────────
        return JsonResponse(
            {
                "success": True,
                "document_type": document_type,
                "data": fields,
                "record_id": record_id,
            },
            status=200,
        )

    except Exception as e:
        print(f"--- [UPLOAD] UNHANDLED ERROR: {e} ---")
        import traceback
        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=500)
