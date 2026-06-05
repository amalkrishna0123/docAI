import json
from unittest.mock import patch
from django.test import TestCase, Client
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import UAEDocumentTOB, UAEDocumentPassport

class TOBDocumentTests(TestCase):
    def setUp(self):
        self.client = Client()

    @patch('document_tests.views.google_document_ai_ocr')
    @patch('document_tests.views.call_gemini_ai')
    def test_tob_approved_scenario(self, mock_call_gemini_ai, mock_ocr):
        # Mock OCR output
        mock_ocr.return_value.text = "Flexi Health Insurance Table of Benefits Outpatient Treatment Outpatient Benefits"
        
        # Mock Gemini Response (approved TOB with signature)
        mock_call_gemini_ai.return_value = {
            "document_type": "TOB",
            "data": {
                "matched_keywords": [
                    "Flexi Health Insurance",
                    "Table of Benefits",
                    "Outpatient Treatment"
                ],
                "signature_present": True,
                "signature_pages": [1],
                "signature_locations": ["bottom center"],
                "signature_status": "approved",
                "validation_status": "approved",
                "decline_reason": ""
            }
        }
        
        # Upload a dummy PDF
        file = SimpleUploadedFile("dummy.pdf", b"pdf_content", content_type="application/pdf")
        response = self.client.post(
            '/api/upload-document/',
            {'document': file},
            HTTP_X_SELECTED_DOC_TYPE="TOB"
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Check step 4 output structure
        self.assertEqual(data["document_type"], "TOB")
        self.assertEqual(data["signature_present"], True)
        self.assertEqual(data["validation_status"], "approved")
        self.assertEqual(data["decline_reason"], "")
        self.assertIn("Flexi Health Insurance", data["matched_keywords"])
        
        # Verify persistence in database
        self.assertEqual(UAEDocumentTOB.objects.count(), 1)
        record = UAEDocumentTOB.objects.first()
        self.assertEqual(record.document_type, "TOB")
        self.assertEqual(record.signature_present, True)
        self.assertEqual(record.validation_status, "approved")
        self.assertIn("Flexi Health Insurance", json.loads(record.matched_keywords))

    @patch('document_tests.views.google_document_ai_ocr')
    @patch('document_tests.views.call_gemini_ai')
    def test_tob_declined_signature_missing_scenario(self, mock_call_gemini_ai, mock_ocr):
        # Mock OCR output
        mock_ocr.return_value.text = "Flexi Health Insurance Table of Benefits"
        
        # Mock Gemini Response (TOB but no signature)
        mock_call_gemini_ai.return_value = {
            "document_type": "TOB",
            "data": {
                "matched_keywords": [
                    "Flexi Health Insurance",
                    "Table of Benefits"
                ],
                "signature_present": False,
                "signature_pages": [],
                "signature_locations": [],
                "signature_status": "declined",
                "validation_status": "declined",
                "decline_reason": "Signature not found"
            }
        }
        
        file = SimpleUploadedFile("dummy.pdf", b"pdf_content", content_type="application/pdf")
        response = self.client.post(
            '/api/upload-document/',
            {'document': file},
            HTTP_X_SELECTED_DOC_TYPE="TOB"
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(data["document_type"], "TOB")
        self.assertEqual(data["signature_present"], False)
        self.assertEqual(data["validation_status"], "declined")
        self.assertEqual(data["decline_reason"], "Signature not found")
        
        # Verify database
        self.assertEqual(UAEDocumentTOB.objects.count(), 1)
        record = UAEDocumentTOB.objects.first()
        self.assertEqual(record.document_type, "TOB")
        self.assertEqual(record.signature_present, False)
        self.assertEqual(record.validation_status, "declined")
        self.assertEqual(record.decline_reason, "Signature not found")

    @patch('document_tests.views.google_document_ai_ocr')
    @patch('document_tests.views.call_gemini_ai')
    def test_non_tob_unknown_scenario(self, mock_call_gemini_ai, mock_ocr):
        # Mock OCR output
        mock_ocr.return_value.text = "Random text here"
        
        # Mock Gemini Response (Not a TOB, no signature)
        mock_call_gemini_ai.return_value = {
            "document_type": "Unknown",
            "data": {
                "matched_keywords": [],
                "signature_present": False,
                "signature_pages": [],
                "signature_locations": [],
                "signature_status": "declined",
                "validation_status": "declined",
                "decline_reason": "Document is not a TOB and signature not found"
            }
        }
        
        file = SimpleUploadedFile("dummy.pdf", b"pdf_content", content_type="application/pdf")
        response = self.client.post(
            '/api/upload-document/',
            {'document': file},
            HTTP_X_SELECTED_DOC_TYPE="TOB"
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(data["document_type"], "Unknown")
        self.assertEqual(data["signature_present"], False)
        self.assertEqual(data["validation_status"], "declined")
        self.assertEqual(data["decline_reason"], "Document is not a TOB and signature not found")
        
        # Verify database
        self.assertEqual(UAEDocumentTOB.objects.count(), 1)
        record = UAEDocumentTOB.objects.first()
        self.assertEqual(record.document_type, "Unknown")
        self.assertEqual(record.decline_reason, "Document is not a TOB and signature not found")

    @patch('document_tests.views.google_document_ai_ocr')
    @patch('document_tests.views.call_gemini_ai')
    def test_passport_preserves_functionality(self, mock_call_gemini_ai, mock_ocr):
        # Mock OCR output
        mock_ocr.return_value.text = "PASSPORT NUMBER V1234567"
        
        # Mock Gemini Response for Passport
        mock_call_gemini_ai.return_value = {
            "document_type": "Passport",
            "data": {
                "passport_number": "V1234567",
                "full_name": "JOHN DOE",
                "nationality": "Indian",
                "date_of_birth": "01/01/1990",
                "issuing_date": "01/01/2020",
                "expiry_date": "01/01/2030",
                "stamp_date": ""
            }
        }
        
        file = SimpleUploadedFile("passport.jpg", b"jpeg_content", content_type="image/jpeg")
        response = self.client.post(
            '/api/upload-document/',
            {'document': file}
        )
        
        # The Passport response has success wrapper
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(data["success"], True)
        self.assertEqual(data["document_type"], "Passport")
        self.assertEqual(data["data"]["passport_number"], "V1234567")
        self.assertIn("record_id", data)
        
        # Verify passport is created, and NO TOB record is created
        self.assertEqual(UAEDocumentPassport.objects.count(), 1)
        self.assertEqual(UAEDocumentTOB.objects.count(), 0)
