import logging
from datetime import datetime
from document_tests.google_document_ai import google_document_ai_ocr
from document_tests.ai_extractor import build_extraction_prompt, call_gemini_ai

logger = logging.getLogger(__name__)

class EmiratesIDExtractor:
    def __init__(self, api_key=None):
        pass

    def process_pdf(self, document, employment_type='Employee'):
        """
        Process document using AI extraction logic (Google Document AI + Gemini AI).
        """
        try:
            if hasattr(document, 'seek'):
                document.seek(0)
            file_bytes = document.read()
            
            mime_type = "application/pdf" if getattr(document, 'name', '').lower().endswith('.pdf') else "image/jpeg"
            
            # 1. OCR using Google Document AI
            raw_text = google_document_ai_ocr(file_bytes, mime_type)
            
            if not raw_text or len(raw_text.strip()) < 10:
                logger.error("OCR failed or returned minimal text.")
                return {"error": "OCR failed to extract text."}
            
            # 2. AI Extraction using Gemini AI
            prompt = build_extraction_prompt(raw_text)
            ai_result = call_gemini_ai(prompt)
            
            if "error" in ai_result:
                return {"error": ai_result["error"]}
            
            fields = ai_result.get("data", {})
            
            def _format_date(date_str):
                if not date_str:
                    return None
                try:
                    import re
                    date_str = date_str.strip()
                    if "-" in date_str and len(date_str.split("-")[0]) == 4:
                        return date_str
                    clean = re.sub(r'[^\d]', ' ', date_str).split()
                    if len(clean) >= 3:
                        d, m, y = clean[0], clean[1], clean[-1]
                        if len(y) == 2: y = "20" + y
                        if len(d) == 4:
                            return f"{d}-{m.zfill(2)}-{clean[-1].zfill(2)}"
                        else:
                            return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
                    return date_str
                except Exception:
                    return date_str

            def _format_gender(gender_str):
                g = str(gender_str).strip().upper() if gender_str else ""
                if g in ["M", "MALE"]: return "Male"
                if g in ["F", "FEMALE"]: return "Female"
                return gender_str or "Male"

            # Map AI result to Insurance Application schema
            return {
                'emirates_id': fields.get('emirates_id'),
                'full_name': fields.get('name') or fields.get('full_name'),
                'date_of_birth': _format_date(fields.get('dob') or fields.get('date_of_birth')),
                'issuing_date': _format_date(fields.get('issuing_date')),
                'expiry_date': _format_date(fields.get('expiry_date')),
                'nationality': fields.get('nationality'),
                'gender': _format_gender(fields.get('gender')),
                'issuing_place': fields.get('issuing_place', 'Dubai'),
                'occupation': fields.get('occupation', ''),
                'sponsor_name': fields.get('employer') or fields.get('family_sponsor_name') or fields.get('sponsor_name', ''),
            }

        except Exception as e:
            logger.error(f"AI Extraction Failed (EID): {e}")
            return {"error": str(e)}

class PassportExtractor(EmiratesIDExtractor):
    def process_passport(self, document):
        try:
            if hasattr(document, 'seek'):
                document.seek(0)
            file_bytes = document.read()
            mime_type = "application/pdf" if getattr(document, 'name', '').lower().endswith('.pdf') else "image/jpeg"
            
            raw_text = google_document_ai_ocr(file_bytes, mime_type)
            prompt = build_extraction_prompt(raw_text)
            ai_result = call_gemini_ai(prompt)
            
            if "error" in ai_result:
                return {"error": ai_result["error"]}
            
            fields = ai_result.get("data", {})
            return {
                'passport_number': fields.get('passport_number'),
                'full_name': fields.get('full_name'),
                'expiry_date': fields.get('expiry_date'),
                'nationality': fields.get('nationality'),
                'date_of_birth': fields.get('date_of_birth') or fields.get('dob'),
                'issuing_date': fields.get('issuing_date')
            }
        except Exception as e:
            logger.error(f"AI Extraction Failed (Passport): {e}")
            return {"error": str(e)}

class VisaExtractor(EmiratesIDExtractor):
    def process_visa(self, document):
        try:
            if hasattr(document, 'seek'):
                document.seek(0)
            file_bytes = document.read()
            mime_type = "application/pdf" if getattr(document, 'name', '').lower().endswith('.pdf') else "image/jpeg"
            
            raw_text = google_document_ai_ocr(file_bytes, mime_type)
            prompt = build_extraction_prompt(raw_text)
            ai_result = call_gemini_ai(prompt)
            
            if "error" in ai_result:
                return {"error": ai_result["error"]}
            
            fields = ai_result.get("data", {})
            return {
                'visa_number': fields.get('file_number') or fields.get('id_number') or fields.get('visa_no'),
                'full_name': fields.get('name') or fields.get('full_name'),
                'expiry_date': fields.get('expiry_date'),
                'file_number': fields.get('file_number'),
                'emirates_id_number': fields.get('emirates_id_number') or fields.get('emirates_id'),
                'passport_number': fields.get('passport_no') or fields.get('passport_number'),
                'issuing_date': fields.get('issuing_date'),
                'profession': fields.get('profession') or fields.get('occupation'),
                'family_head_employer': fields.get('family_head_employer') or fields.get('sponsor_name')
            }
        except Exception as e:
            logger.error(f"AI Extraction Failed (Visa): {e}")
            return {"error": str(e)}
