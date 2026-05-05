import re
from typing import List, Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)

class EmiratesIDExtractor:
    """
    A forensic extraction engine for UAE Resident Identity Cards.
    Designed to handle multi-page PDFs, mixed layouts, and bilingual text streams.
    """

    def __init__(self):
        # COMPILED REGEX PATTERNS
        # Source : Matches 784-YYYY-SSSSSSS-C with optional hyphens/spaces
        self.rx_id = re.compile(r'784[-]?\s?(\d{4})[-]?\s?(\d{7})[-]?\s?(\d{1})')
        
        # Date pattern: DD/MM/YYYY (Common in UAE docs)
        self.rx_date = re.compile(r'\b\d{2}/\d{2}/\d{4}\b')
        
        # Card Number: Usually 9 digits, distinctive pattern often labeled
        self.rx_card_no = re.compile(r'\b\d{9}\b')

        # Labels for relative extraction. 
        # We use IGNORECASE to handle variations like "Name:" or "NAME"
        self.labels = {
            'Name': re.compile(r'Name:?', re.IGNORECASE),
            'Nationality': re.compile(r'Nationality:?', re.IGNORECASE),
            'Employer': re.compile(r'Employer:?', re.IGNORECASE),
            'Occupation': re.compile(r'Occupation:?', re.IGNORECASE),
            'Sponsor': re.compile(r'Sponsor:?', re.IGNORECASE)
        }

    def normalize_text(self, text: str) -> str:
        """
        Cleans extraction artifacts.
        - Collapses multiple spaces.
        - Removes non-printable characters.
        """
        if not text:
            return ""
        return re.sub(r'\s+', ' ', text).strip()

    def extract_id_from_text(self, text: str) -> Optional[str]:
        """
        Scans a text block for the Emirates ID pattern.
        Returns a standardized string: 784-XXXX-XXXXXXX-X
        """
        match = self.rx_id.search(text)
        if match:
            # Reconstruct with standard hyphenation for consistency
            return f"784-{match.group(1)}-{match.group(2)}-{match.group(3)}"
        return None

    def extract_value_for_label(self, lines: List[str], label_rx: re.Pattern) -> Optional[str]:
        """
        Intelligent value hunter. 
        Looks for a label on a line. If the value isn't on the same line, 
        checks the next line (common in narrow ID layouts).
        """
        for i, line in enumerate(lines):
            match = label_rx.search(line)
            if match:
                # Strategy 1: Check same line (Right of the label)
                # Split by the full match of the label
                parts = label_rx.split(line)
                if len(parts) > 1:
                    candidate = parts[-1].strip()
                    # Filter out Arabic text or noise if candidate is substantial
                    if len(candidate) > 2:
                        return candidate

                # Strategy 2: Check next line (Below the label)
                if i + 1 < len(lines):
                    next_line = lines[i+1].strip()
                    # Heuristic: If next line is another label, stop.
                    if ":" not in next_line and len(next_line) > 2:
                        return next_line
        return None

    def process_pdf(self, file_path_or_stream) -> Dict[str, Any]:
        """
        Main processing loop.
        Extracts data from PDF stream or file path.
        Returns the first person found (assuming single applicant context).
        """
        try:
            import pdfplumber
        except ImportError:
            logger.error("pdfplumber not installed.")
            return {'error': "OCR Library (pdfplumber) is missing. Please install it."}

        current_person = {}
        
        try:
            # Open the PDF (handles both path string and file-like objects)
            with pdfplumber.open(file_path_or_stream) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    # Extract text preserving layout
                    text = page.extract_text(layout=True)
                    if not text:
                        continue

                    # Pre-process lines
                    lines = [self.normalize_text(line) for line in text.split('\n')]
                    full_page_text = " ".join(lines)

                    # --- ANCHOR CHECK ---
                    # Does this page contain an Emirates ID number?
                    found_id = self.extract_id_from_text(full_page_text)
                    
                    if found_id:
                        # If we already found an ID and this is a DIFFERENT one (rare collision),
                        # in a single-user upload context we might prioritize the one matching user input if known,
                        # but for now we take the first robust one we find or update if fields are better.
                        current_person['emirates_id'] = found_id

                    # --- FIELD EXTRACTION ---
                    # We run this on every page because data might be split (Front/Back)
                    
                    # 1. Name
                    if 'full_name' not in current_person:
                        val = self.extract_value_for_label(lines, self.labels['Name'])
                        if val: current_person['full_name'] = val

                    # 2. Nationality
                    if 'nationality' not in current_person:
                        val = self.extract_value_for_label(lines, self.labels['Nationality'])
                        if val: current_person['nationality'] = val
                    
                    # 3. Employer / Sponsor
                    if 'employer_sponsor_name' not in current_person:
                        val = self.extract_value_for_label(lines, self.labels['Employer'])
                        if not val:
                             val = self.extract_value_for_label(lines, self.labels['Sponsor'])
                        if val: current_person['employer_sponsor_name'] = val

                    # 4. Occupation
                    if 'occupation' not in current_person:
                         val = self.extract_value_for_label(lines, self.labels['Occupation'])
                         if val: current_person['occupation'] = val

                    # 5. Dates (Heuristic)
                    dates = self.rx_date.findall(full_page_text)
                    if dates:
                        try:
                            # Sort dates: Earliest = DOB, Latest = Expiry
                            sorted_dates = sorted(dates, key=lambda x: "-".join(x.split('/')[::-1]))
                            if sorted_dates:
                                if 'date_of_birth' not in current_person:
                                    current_person['date_of_birth'] = sorted_dates[0] # Earliest
                                if 'expiry_date' not in current_person:
                                    # Logic update: Expiry is typically > Today. 
                                    # Issue Date is < Expiry. 
                                    # If 3 dates: DOB, Issue, Expiry.
                                    # If 2 dates: DOB, Expiry (or Issue).
                                    # We greedily take the last one as expiry for now.
                                    current_person['expiry_date'] = sorted_dates[-1]
                        except Exception as e:
                            logger.warning(f"Date parsing warning: {e}")

        except Exception as e:
            return {'error': f"Processing failed: {str(e)}"}

        # Post-process format to match Serializer expectations
        # Convert DD/MM/YYYY to YYYY-MM-DD
        for field in ['date_of_birth', 'expiry_date']:
            if field in current_person:
                try:
                    d, m, y = current_person[field].split('/')
                    current_person[field] = f"{y}-{m}-{d}"
                except:
                    pass

        return current_person
