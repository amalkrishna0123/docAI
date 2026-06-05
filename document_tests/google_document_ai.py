from google.cloud import documentai
from google.api_core.client_options import ClientOptions
import os
from datetime import datetime
from django.conf import settings

PROJECT_ID = "warm-choir-291413"
LOCATION = "us"
PROCESSOR_ID = "3ec2438d05c1ce38" 

# Explicitly set credentials path
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "google-key.json")

# Global client to reuse connections
_client = None

def log_timing(message):
    try:
        log_file = settings.BASE_DIR / "extraction_performance.log"
        with open(log_file, "a") as f:
            f.write(f"[{datetime.now()}] [OCR] {message}\n")
    except:
        pass
    print(f"--- [OCR] {message} ---")

def _get_client():
    global _client
    if _client is None:
        log_timing("Initializing Document AI client...")
        opts = ClientOptions(api_endpoint=f"{LOCATION}-documentai.googleapis.com")
        _client = documentai.DocumentProcessorServiceClient(client_options=opts)
    return _client

def google_document_ai_ocr(file_bytes, mime_type):
    """
    Extract raw text from a document using Google Document AI.
    Reuses the client connection for better performance on subsequent requests.
    """
    try:
        log_timing("OCR started")
        client = _get_client()
        name = client.processor_path(PROJECT_ID, LOCATION, PROCESSOR_ID)

        raw_document = documentai.RawDocument(
            content=file_bytes,
            mime_type=mime_type
        )

        request = documentai.ProcessRequest(
            name=name,
            raw_document=raw_document,
            imageless_mode=False
        )

        start = datetime.now()
        result = client.process_document(request=request)
        end = datetime.now()
        duration = (end - start).total_seconds()
        
        log_timing(f"OCR process_document finished in {duration:.2f}s")
        return result.document
    except Exception as e:
        log_timing(f"Google Document AI error: {e}")
        return None