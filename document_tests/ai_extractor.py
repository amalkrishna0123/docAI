"""
ai_extractor.py

AI-based structured document extraction using Google Gemini.
Replaces regex-based parser_logic.py for all UAE document types.

Supported document types (auto-detected):
  - Passport
  - Emirates ID
  - UAE Visa
  - Labour Contract
  - Travel History
"""

import json
import os
import re
import time
from google import genai
from google.genai import types
from django.conf import settings
from datetime import datetime

# Global client to reuse connections (Best practice for performance)
_genai_client = None

def _get_genai_client():
    global _genai_client
    if _genai_client is None:
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if api_key:
            _genai_client = genai.Client(api_key=api_key)
    return _genai_client

# Prompt Builder

def build_extraction_prompt(ocr_text: str, requested_doc_type: str = "") -> str:
    """
    Build a structured extraction prompt that instructs the AI to:
      1. Auto-detect the document type from the OCR text.
      2. Extract only the required fields for that document type.
      3. Return a strict JSON object — no markdown, no explanation.

    The prompt is deliberately explicit about noise handling because
    Google Document AI output can contain Arabic characters, layout
    artifacts, repeated headers, and garbled text.
    """

    # Truncate OCR text to keep the prompt within reasonable token limits.
    # 15,000 chars is usually enough for multi-page Labour Contracts.
    MAX_OCR_CHARS = 80000
    safe_text = ocr_text[:MAX_OCR_CHARS] if len(ocr_text) > MAX_OCR_CHARS else ocr_text
    if len(ocr_text) > MAX_OCR_CHARS:
        print(f"--- [AI] WARNING: Truncating OCR text from {len(ocr_text)} to 15,000 chars ---")

    prompt = f"""
You are a document extraction AI for UAE government documents.

You will receive OCR text from a document. The text may contain Arabic,
English, noise, or repeated headers.

Your job:
1. Identify the document type.
{f"   - IMPORTANT: The user has specifically requested: '{requested_doc_type}'. Scan for this document type." if requested_doc_type else ""}
2. Extract required fields.
   - If multiple documents are present in the text, extract ONLY the details for the requested type.
3. Return ONLY valid JSON.

Never return explanations, markdown, or comments.

----------------------------------------
DOCUMENT TYPES
----------------------------------------

1) Passport
Detect if text contains:
Passport No / Passport Number
Nationality
Date of Birth
Issuing Date
Expiry Date


NAME EXTRACTION RULE (STRICT):
- Passports often list Surname first, followed by Given Names.
- You MUST extract the name in this order: [First Given Name] [Middle Name(s) if any] [Last Surname].
- Do NOT return [Surname] [Given Name].
- Example: If OCR says "Surname: SMITH, Given Names: JOHN JACOB", you MUST return "JOHN JACOB SMITH".
- Apply this rule to ALL name fields (full_name, employee_name, etc.) across all document types.

ANTI-CONFUSION RULE:
- DO NOT classify as Passport if "COC reference" or "Certificate of Continuity" exists. COC always takes priority.

2) Emirates ID
Detect if text contains:
UNITED ARAB EMIRATES
IDENTITY CARD
ID Number / ID No: 784- (Format: 784-YYYY-XXXXXXX-X)

CARD TYPE EXTRACTION:
- If OCR text contains "Golden Card" or "Golden Visa", set "card_type": "Golden Visa".
- Otherwise, set "card_type": "".
- NORMALIZATION: Always return "Golden Visa". Never return "Golden Card".

ANTI-CONFUSION RULE:
- DO NOT classify as Emirates ID if "COC reference" or "Certificate of Continuity" exists. COC always takes priority.

Important: 
Emirates IDs for residents often contain the word "RESIDENT". 
If you see "IDENTITY CARD" and a 784 ID number, it is ALWAYS an Emirates ID, even if it says "RESIDENT".

3) UAE Visa (Classification Rules)

- eVisa Identification: 
  If the document contains the word "eVisa" anywhere → it is eVisa. 
  Even if "Residence" appears, "eVisa" always wins.

- Residence Visa Identification:
  If "file number" is present and it is NOT an eVisa → it is Residence Visa.
  Residence visas will NOT have a permit number.

Decision Priority:
1. IF "eVisa" detected → document_type = "eVisa"
2. ELSE IF "file number" detected → document_type = "Residence Visa"
3. ELSE → fallback to document_type = "UAE Visa" (using existing detected signals)

Extraction Rules for eVisa:
- permit_number: Extract the value labeled as "Entry Permit No" or "Permit No". It ALMOST ALWAYS follows a slash format (e.g., 101/2025/1/1234567). 
- IMPORTANT: Do NOT extract long numeric strings (e.g., 021012...) that look like barcodes; these are NOT permit numbers.
- issuing_date: Search for "Date of Issue", "Issue Date", "Date & Place of Issue", or "تاريخ الإصدار".
- Extract: permit_number, uid_no, passport_no, name, nationality, profession, issuing_date, sponsor_name, employer.
- sponsor_name: Extract family sponsor name if applicable.
- employer: Extract establishment/company name if applicable.
- Do NOT extract: expiry_date.

Extraction Rules for Residence Visa:
- issuing_date: Search for "Issue Date", "Date of Issue", or "تاريخ الإصدار".
- expiry_date: Search for "Expiry Date" or "تاريخ الانتهاء".
- file_number: Extract the value with slashes (e.g., 101/2024/1/123456).
- Extract: file_number, emirates_id, issuing_date, expiry_date, passport_no, name, profession, sponsor_name, employer.
- sponsor_name: Extract family sponsor name if applicable.
- employer: Extract establishment/company name if applicable.
- Do NOT extract: nationality, uid_no.

----------------------------------------
STAMP DATE EXTRACTION (CRITICAL - IMAGE BASED)
----------------------------------------
You MUST extract "stamp_date" from BOTH:
1) eVisa documents (entry stamp or "Change Status" seal)
2) Passport documents (entry stamp)

This field is NOT part of normal printed text. It exists inside a STAMP / SEAL.

STRICT RULES:
1. LOCATION:
   - Passport: Usually at the bottom of the page, often curved or rotated inside a circular or oval seal.
   - eVisa: Usually overlaid as a round or oval stamp, sometimes overlapping text or photo. Often at the bottom center.
2. APPEARANCE:
   - Stamp text may be curved, rotated, faint, or partially overlapping.
   - Date may be TEXT-based (e.g., 16 APR 2026) or NUMERIC (e.g., 25/04/2026 or 14/4/2026).
   - Valid stamps include Airport Entry stamps and circular "Change Status" seals (marked "Change Status" or "تعديل وضع").
3. EXTRACTION PRIORITY:
   - ONLY extract date INSIDE the stamp/seal.
   - The stamp date often differs from the printed issuing_date (e.g. stamp might be days later). Extract it anyway.
4. FORMAT:
   - Always return in format: DD MMM YYYY (Example: 09 APR 2026).
   - If numeric date is found (e.g. 25/04/2026), convert it to (25 APR 2026).
5. ANTI-HALLUCINATION:
   - If the stamp date is not clearly visible → return ""
   - DO NOT guess. However, if a numeric date is clearly visible inside a seal, it IS a valid stamp date.
   - DO NOT be afraid to extract a date that differs from the issue date if it's inside a stamp.
6. MULTIPLE DATES IN STAMP:
   - If multiple dates appear, choose the most prominent central stamp date.

----------------------------------------
UAE VISA CRITICAL EXTRACTION RULES (STRICT)
----------------------------------------
1. PERMIT NUMBER (eVisa):
   - MUST be the value following the "/" format (e.g., 101/2025/3/...).
   - MUST NOT be a long continuous numeric sequence (e.g., 021012...). If you see a long number without slashes, it is a Barcode/Serial — IGNORE IT.
   - If no slash-formatted number is found, return "".

2. ISSUING DATE (Both types):
   - You MUST look for "Issue Date", "Date of Issue", or "تاريخ الإصدار".
   - It is often near the bottom of the page or in a dedicated "Issue Information" box.
   - If the date is missing but you see a year in the permit/file number (e.g., 2024), double-check nearby text for a full DD/MM/YYYY date.

3. SPONSOR & EMPLOYER:
   - Extract "sponsor_name" if it's a personal/family sponsor.
   - Extract "employer" if it's a company name.
   - If only one entity is present and its nature is unclear, put it in "sponsor_name".
Detect if text contains:
Employment Contract
MOHRE
Ministry of Human Resources
Establishment details

----------------------------------------
LABOUR CONTRACT EXTRACTION
----------------------------------------

Extract values from English labels only.
Ignore Arabic text.

Fields:

establishment_name
establishment_number
employer_representative
emirate
employer_email
employer_phone
work_style
transaction_number
contract_type
contract_issue_date
employee_name
employee_nationality
employee_dob
employee_passport_no
employee_qualification
employee_phone
job_title
work_hours
weekly_rest
annual_leave
contract_start_date
contract_end_date
approval_date
total_salary

5) Continuity Certificate (COC) [HIGH PRIORITY DETECTION]

This document can have MANY formats and insurers (Dubai Insurance, Daman, Oman Insurance, etc.).

DETECTION RULES:
Detect if ANY of the following PRIMARY KEYWORDS exist:
- "Certificate of Continuity"
- "Continuity Certificate"
- "Health Insurance Certificate of Continuity"
- "COC reference"
- "COC Reference No"
- "DOH COC reference"

SECONDARY CONFIRMATION (at least one should also exist):
- "insured"
- "policy number"
- "coverage period"
- "Effective Date" AND "Expiry Date"

IMPORTANT PRIORITY RULE:
- If COC keywords are found → ALWAYS classify as "COC"
- EVEN IF Emirates ID or Passport data appears in the document.
- IGNORE ID card sections, barcodes, or unrelated pages if COC indicators are present.

MULTI-PAGE RULE:
- If any page contains COC indicators → the entire document is COC.

ANTI-CONFUSION RULE:
- DO NOT classify as Passport or Emirates ID if "COC reference" or "Certificate of Continuity" exists.

Extract:
- insured_name (Map from "Member Name")
- policy_holder_name (Map from "Policy Holder Name")
- policy_number
- policy_expiry_date
- inception_date (or Effective Date)
- insured_until
- coc_reference_no
- coc_validity_date
- issue_date
- insurer_name
- gender
- date_of_birth

STRICT RULES FOR COC:
1. NAME MAPPING:
   - "Member Name" ALWAYS maps to insured_name.
   - "Policy Holder Name" ALWAYS maps to policy_holder_name.
   - If only one name exists, set policy_holder_name to "".
   - Do NOT mix, swap, or confuse these two names.
2. DATE OF BIRTH:
   - ONLY extract if explicitly labeled as "Date of Birth", "DOB", or "تاريخ الميلاد".
   - Do NOT confuse with "Effective Date", "Expiry Date", "Inception Date", or "Issue Date".
   - If not explicitly present as DOB, return "".
3. POLICY DATES:
   - inception_date maps from "Effective Date" or "Inception Date".
   - policy_expiry_date maps from "Expiry Date" or "Policy Expiry Date".

6) Residence Cancellation

Detect if text contains:
"Residence Cancellation"
"Cancel Date"

Extract:
uid_no
emirates_id
residence_no
passport_no
full_name
profession
employer
place_of_issue
cancel_date

Rules:
- residence_no is slash formatted (e.g. 401/2024/2/174132)
- passport_no may start with a letter
- do NOT confuse cancel_date with printing_date

8) Travel History
Detect if text contains:
"My Transactions"
"From Date"
"To Date"
"Transaction Date"
"Port Name"
"Entry / Exit"

If detected → document_type = "Travel History"

Extract:
- passport_no (Travel Passport No)
- name (Full Name (En))
- from_date (Format: DD/MM/YYYY)
- to_date (Format: DD/MM/YYYY)
- transaction_date (Format: DD/MM/YYYY)
- transaction_type (ENTRY / EXIT)
- port_name

9) Business Licence (Commercial Registration / Economic Licence)

Detect if text contains ANY of:
- "Economic Licence"
- "Commercial Registration Certificate"
- "Licence No"
- "Trade Name"
- "Licence Type"
- "ADRA"
- "Department of Economic Development"

MULTI-PAGE RULE:
- If any page contains structured licence table → classify entire document as Business Licence

----------------------------------------
EXTRACT FIELDS
----------------------------------------

core identifiers:
- licence_number (Economic Licence No or Licence No)
- registry_number
- unified_registration_number
- customs_registration_number

company details:
- trade_name
- legal_form
- licence_type (Business / Industrial / etc.)
- licence_category (Normal / Special / etc.)

dates:
- establishment_date
- issuance_date
- expiry_date

financial:
- paid_up_capital
- paid_up_capital_in_words

government ids:
- adcci_number
- mohre_establishment_number
- icp_establishment_number

ownership:
- owner_name
- owner_nationality
- owner_role
- share_percentage

contact:
- official_email
- official_mobile
- address

activities:
- activity_name
- activity_code

7) Medical Application Form (MAF)

Detect if text contains:
Medical Application Form
Dubai Insurance
Insurance History
Active at work Since

The document may contain multiple pages. Information may appear in tables,
checkbox lists, or later pages such as KYC forms.

Prioritize extracting values from structured tables and checkbox lists.
Do not analyze unrelated sections once the value is found.

----------------------------------------
ADVANCED CHECKBOX INTERPRETATION (STRICT - VISUAL POSITION BASED)
----------------------------------------

Medical forms (especially Dubai Insurance) use a two-column checkbox layout for each medical question.

CRITICAL: DO NOT interpret based only on the symbol type (X, ✓, /, etc.).
You MUST determine the answer based ONLY on WHICH CHECKBOX COLUMN contains the mark.

Step-by-step Visual Logic:

1. Identify the row for the question visually.
2. Locate the pair of checkboxes aligned to that row.
3. Identify the column meaning:
   - The LEFT checkbox in the pair ALWAYS means "Yes".
   - The RIGHT checkbox in the pair ALWAYS means "No".
4. Detect ANY visible mark inside either checkbox (tick, X, slash, pen stroke, scribble, blue/black ink mark, partial mark).
5. Interpret result:
   - Mark inside LEFT checkbox => "Yes"
   - Mark inside RIGHT checkbox => "No"
6. If BOTH boxes contain marks OR NEITHER box is clearly marked:
   - Return empty string ""

DUBAI INSURANCE SPECIAL LAYOUT RULE:
- Questions 1 to 11: Located on the LEFT side of the page; checkboxes are near the page center.
- Questions 13 to 23: Located on the RIGHT side of the page; checkboxes are near the far-right side.
- For EVERY medical question row, there are exactly TWO boxes: LEFT=YES, RIGHT=NO.

TEXT OVERRIDE RULE (PRIORITY 1):
- If handwritten or printed text explicitly says "YES" or "NO" (or "Y"/"N") near the question, ALWAYS prioritize this explicit text over checkbox detection.
- Example: Handwritten "NO" or circled "NO" overrides any checkbox marks.

HANDWRITTEN MARK RULES:
- Treat ALL of the following as valid marks: X, ✓, /, diagonal line, scribble, partial mark, small tick.
- If the mark overlaps mostly inside one checkbox, treat that checkbox as selected.

ANTI-ERROR RULES:
- DO NOT assume X = No.
- DO NOT assume tick = Yes.
- DO NOT assume blank = No.
- DO NOT infer based on question meaning.
- DO NOT default answers automatically. ONLY use checkbox POSITION.
- If unsure, return "".

FINAL DECISION PRIORITY:
1. Explicit YES/NO text
2. Left/right checkbox visual position
3. Otherwise return ""

EXTRACT FIELDS

# Applicant Info
insured_name
application_date (Format: DD/MM/YYYY)
required_plan
application_policy_no
current_address
active_at_work_since (Text or Date)

# Personal Details
nationality
gender
date_of_birth (Format: DD/MM/YYYY)
marital_status
height_cm
weight_kg
uae_resident (Yes/No)
already_insured (Yes/No)
insured_since

# Insurance History
insurance_substandard_terms (Yes/No)
insurance_declined (Yes/No)
hazardous_sports (Yes/No)
hazardous_sports_details

# Medical Questions
# For these, look for the EXACT question strings below and check the YES/NO columns.
infectious_diseases: "Infectious and parasitic diseases"
cancer: "Cancer, Neoplasms, Tumors? (specify below the type, location, treatment, whether malignant or benign)"
endocrine_diseases: "Diseases of the endocrine system, nutritional-, metab Endocrine, Nutritional, Metabolic and/or Immunity System? (i.e. diabetes, thyroid or pituitary gland problems, adrenal gland, ovary or testes problems, hormone problems, gout, multiple sclerosis, cystic fibrosis, metabolic disorders, immune problems, etc.)"
blood_disorders: "Blood & Blood Forming Organ Systems? (i.e. anemia, thalassaemia, bleeding disorders, blood cell disease, spleen problems, lymph node problems, etc.)"
mental_disorders: "Mental-/psychiatric disorders"
nervous_system: "Nervous System or Sense Organs? (i.e. ear injury/infection, vertigo, hearing problems, eye injury/disease, retina problems, glaucoma, vision problems, muscular dystrophy, brain/nerve degeneration, meningitis, paralysis, seizures, epilepsy, neuralgia, etc.)"
cardiovascular: "Cardiovascular System? (i.e. stroke, cerebral ischemia, rheumatic fever, atherosclerosis, aneurysm, embolism, peripheral vascular disease, hypertension, heart valve disease, irregular heartbeat, pulmonary embolism, phlebitis, varicosities, etc.)"
respiratory: "Respiratory System? (i.e. Sinusitis, allergies, tonsillitis/laryngitis, bronchitis, emphysema, pneumonia, etc.)"
digestive_system: "9. Cirrhosis/ Hepatitis / Wilsons disease / Pancreatitis/ Liver disease / Cohn's disease / Ulcerative Colitis /Piles or any other disease of Mouth, Esophagus, Liver, Gall bladder, Stomach or Intestines or any other part of Digestive System?"
genitourinary: "Genitourinary System? (i.e. Kidney/bladder infections, renal failure, kidney stones, endometriosis, menstrual cycle problems, salpingitis, ovarian cysts, prostate problems, impotence, testicle infections, sperm abnormalities, fertility problems, Breast disorder etc.)"
maternity_history: "11. Do you have earlier history of Caesarean Section, Premature Delivery or Premature babies? Or any other complications related to maternity, till date?"
musculoskeletal: "Musculoskeletal and/or Connective Tissue System? (I.e. fractures, joint or cartilage problems, back problems, bone infections, osteoporosis, arthritis, rheumatism, etc.)"
congenital: "Congenital anomalies, hereditary/genetic diseases"
perinatal: "Certain conditions originating in the perinatal period"
injury_poisoning: "Injury and poisoning"
previous_hospitalization: "Previous medical/surgical hospitalizations, procedures and operations"
chronic_disease: "Any (chronic) disease(s), symptoms and complaints not mentioned above"
pre_existing_disease: "Any Pre-existing disease(s), symptoms and complaints I within the last ten years"
organ_surgery: "Have you ever undergone surgery to remove a body organ or structure or being hospitalized in the past? (Specify body organ/Structure, date & place of surgery?) If Yes, have there been any complications to date?"
good_health: "Are you presently in good health, entirely free from any physical/mental impairment and deformity? If no please provide the details"
weight_change: "Has there been any Loss/Gain of weight in last 12 months?"
smoking_alcohol: "Smoke, consume alcohol, or chew tobacco or use any recreational drugs? If Yes please then provide the frequency and amount consumed"
bone_fractures: "Did you ever have any bone fractures or injuries to bones or tendons? Has any material used for orthopedic aids been removed?"
Shortness_vision: "Any dimness of vision or cataract etc?"
Hepatitis: "Have you been tested or treated for Hepatitis A or C?"
dental_problems: "Have you ever suffered from dental problems?"
dental_details
dental_last_treatment

# Pregnancy
pregnant (Are you currently pregnant?)
pregnancy_complications (Any complications in current/past pregnancies)
last_menstrual_period (LMP date)
trying_to_conceive (Currently trying to get pregnant?)
fertility_treatment (Undergoing fertility treatment?)

# Cancer Section
has_cancer (Diagnosed with cancer?)
cancer_status
cancer_diagnosis
cancer_surgery
cancer_chemotherapy_cycles
cancer_radiotherapy_cycles
cancer_radiation_cycles
cancer_medication
family_cancer_history (FAMILY HISTORY of Cancer?)

Always copy the value exactly from the OCR text.
Do not modify characters.
Do not replace letters with numbers.

10) Table of Benefits (TOB)

STEP 1: DOCUMENT IDENTIFICATION
Classify the document as "TOB" ONLY if the document contains one or more of the following keywords, titles, or section headings (case-insensitive, spacing variations allowed):

PRIMARY KEYWORDS:
- Flexi Health Insurance
- Schedule of Benefits
- ESSENTIAL BENEFIT PLAN
- Table of Benefits
- Outpatient Treatment
- Outpatient Benefits
- Other Additional Benefits
- Other Benefits
- Maternity Services
- Maternity Benefits
- DOH EXCLUSIONS
- INDIVIDUAL MEDICAL INSURANCE
- DHA EXCLUSIONS

DOCUMENT MATCH RULES:
1. If any of the above keywords appear in the title or section headings, the document should be classified as "TOB".
2. Accept both Abu Dhabi DoH and Dubai DHA insurance schedules.
3. Accept minor OCR errors and spacing differences.
4. If none of the keywords are found, classify as "Unknown".
5. IMPORTANT: If requested_doc_type is 'TOB', you must ONLY classify the document as 'TOB' or 'Unknown'. Even if it looks like a Passport or Emirates ID, if it does not meet the TOB criteria, classify it as 'Unknown'.

STEP 2: SIGNATURE DETECTION (IMAGE-BASED)
Use visual analysis of ALL page images, not OCR text alone.

A signature is defined as:
- Handwritten ink marks
- Scribbles or cursive strokes
- Pen-written initials or signatures
- Usually blue, black, or dark ink

Typical locations:
- Bottom of the page
- Top of the page
- Footer area
- Header area
- Any other area on any page

VALID SIGNATURE RULES:
1. Signature may appear on one or more pages.
2. Signature can be partial.
3. Signature can be faint.
4. Signature may overlap printed content.
5. Signature may be located anywhere on the page.
6. Company logos, stamps, printed names, and typed text are NOT signatures.

DECISION RULE:
- If at least one handwritten signature is detected anywhere in the document:
  signature_present = true
  signature_status = "approved"
- If no handwritten signature is detected:
  signature_present = false
  signature_status = "declined"

STEP 3: FINAL VALIDATION
validation_status:
- "approved" if:
    document_type == "TOB"
    AND signature_present == true
- "declined" otherwise

decline_reason:
- "Document is not a TOB" (if document_type != "TOB" and signature_present == true)
- "Signature not found" (if document_type == "TOB" and signature_present == false)
- "Document is not a TOB and signature not found" (if document_type != "TOB" and signature_present == false)
- "" if approved

----------------------------------------
TRAVEL / TRANSACTION TABLE EXTRACTION (PASSPORT & EVISA ONLY)
----------------------------------------
If travel/transaction table data is found AND document_type is Passport or eVisa:
Merge the following fields directly inside the "data" object:

from_date
to_date
transaction_date
transaction_type
port_name

STRICT RULES:

1. FROM / TO DATE:
   - Extract from fields labeled: "From Date", "To Date"
   - Format: DD/MM/YYYY

2. TRANSACTION DATE:
   - Extract ONLY from table column "Transaction Date"
   - DO NOT confuse with issuing_date, expiry_date, or stamp_date

3. MULTIPLE ROWS:
   - If multiple transactions exist → extract ONLY the first visible row

4. MATCHING RULE (CRITICAL):
   - transaction passport_no MUST match visa/passport passport_no
   - transaction name MUST match extracted name
   - If mismatch → IGNORE transaction data completely (set fields to "")

5. ANTI-CONFUSION:
   - DO NOT take dates from visa page
   - DO NOT take stamp date as transaction_date
   - DO NOT guess missing values

----------------------------------------
OUTPUT FORMAT
----------------------------------------

Passport:
{{
  "document_type": "Passport",
  "data": {{
    "passport_number": "",
    "full_name": "",
    "nationality": "",
    "date_of_birth": "",
    "issuing_date": "",
    "expiry_date": "",
    "stamp_date": "",
    "from_date": "",
    "to_date": "",
    "transaction_date": "",
    "transaction_type": "",
    "port_name": ""
  }}
}}

Emirates ID:
{{
  "document_type": "Emirates ID",
  "data": {{
    "emirates_id": "",
    "name": "",
    "nationality": "",
    "gender": "",
    "dob": "",
    "occupation": "",
    "employer": "",
    "issuing_place": "",
    "expiry_date": "",
    "issuing_date": "",
    "family_sponsor_name": "",
    "card_type": ""
  }}
}}

eVisa:
{{
  "document_type": "eVisa",
  "data": {{
    "permit_number": "",
    "uid_no": "",
    "passport_no": "",
    "name": "",
    "nationality": "",
    "profession": "",
    "issuing_date": "",
    "sponsor_name": "",
    "employer": "",
    "stamp_date": "",
    "from_date": "",
    "to_date": "",
    "transaction_date": "",
    "transaction_type": "",
    "port_name": ""
  }}
}}

Travel History:
{{
  "document_type": "Travel History",
  "data": {{
    "passport_no": "",
    "name": "",
    "from_date": "",
    "to_date": "",
    "transaction_date": "",
    "transaction_type": "",
    "port_name": ""
  }}
}}

Residence Visa:
{{
"document_type": "Residence Visa",
"data": {{
"file_number": "",
"emirates_id": "",
"issuing_date": "",
"expiry_date": "",
"passport_no": "",
"name": "",
"profession": "",
"sponsor_name": "",
"employer": ""
}}
}}

UAE Visa (Fallback):
{{
"document_type": "UAE Visa",
"data": {{
"emirates_id": "",
"permit_number": "",
"file_number": "",
"uid_no": "",
"passport_no": "",
"name": "",
"nationality": "",
"profession": "",
"issuing_date": "",
"expiry_date": "",
"sponsor_name": "",
"employer": ""
}}
}}

Labour Contract:
{{
"document_type": "Labour Contract",
"data": {{
"establishment_name": "",
"establishment_number": "",
"employer_representative": "",
"emirate": "",
"employer_email": "",
"employer_phone": "",
"work_style": "",
"transaction_number": "",
"contract_type": "",
"contract_issue_date": "",
"employee_name": "",
"employee_nationality": "",
"employee_dob": "",
"employee_passport_no": "",
"employee_qualification": "",
"employee_phone": "",
"job_title": "",
"work_hours": "",
"weekly_rest": "",
"annual_leave": "",
"contract_start_date": "",
"contract_end_date": "",
"approval_date": "",
"total_salary": ""
}}
}}

Medical Application Form:
{{
"document_type": "Medical Application Form",
"data": {{
"insured_name": "",
"application_date": "",
"required_plan": "",
"application_policy_no": "",
"current_address": "",
"active_at_work_since": "",
"nationality": "",
"gender": "",
"date_of_birth": "",
"marital_status": "",
"height_cm": "",
"weight_kg": "",
"uae_resident": "",
"already_insured": "",
"insured_since": "",
"insurance_substandard_terms": "",
"insurance_declined": "",
"hazardous_sports": "",
"hazardous_sports_details": "",
"infectious_diseases": "",
"cancer": "",
"endocrine_diseases": "",
"blood_disorders": "",
"mental_disorders": "",
"nervous_system": "",
"cardiovascular": "",
"respiratory": "",
"digestive_system": "",
"genitourinary": "",
"maternity_history": "",
"musculoskeletal": "",
"congenital": "",
"perinatal": "",
"injury_poisoning": "",
"previous_hospitalization": "",
"chronic_disease": "",
"pre_existing_disease": "",
"organ_surgery": "",
"good_health": "",
"weight_change": "",
"smoking_alcohol": "",
"bone_fractures": "",
"Shortness_vision": "",
"Hepatitis": "",
"dental_problems": "",
"dental_details": "",
"dental_last_treatment": "",
"pregnant": "",
"pregnancy_complications": "",
"last_menstrual_period": "",
"trying_to_conceive": "",
"fertility_treatment": "",
"has_cancer": "",
"cancer_status": "",
"cancer_diagnosis": "",
"cancer_surgery": "",
"cancer_chemotherapy_cycles": "",
"cancer_radiotherapy_cycles": "",
"cancer_radiation_cycles": "",
"cancer_medication": "",
"family_cancer_history": ""
}}
}}

Continuity Certificate (COC):
{{
"document_type": "COC",
"data": {{
"insured_name": "",
"policy_holder_name": "",
"policy_number": "",
"policy_expiry_date": "",
"inception_date": "",
"insured_until": "",
"coc_reference_no": "",
"coc_validity_date": "",
"issue_date": "",
"insurer_name": "",
"gender": "",
"date_of_birth": ""
}}
}}

Residence Cancellation:
{{
"document_type": "Residence Cancellation",
"data": {{
"uid_no": "",
"emirates_id": "",
"residence_no": "",
"passport_no": "",
"full_name": "",
"profession": "",
"employer": "",
"place_of_issue": "",
"cancel_date": ""
}}
}}

Business Licence:
{{
  "document_type": "Business Licence",
  "data": {{
    "licence_number": "",
    "registry_number": "",
    "unified_registration_number": "",
    "customs_registration_number": "",

    "trade_name": "",
    "legal_form": "",
    "licence_type": "",
    "licence_category": "",

    "establishment_date": "",
    "issuance_date": "",
    "expiry_date": "",

    "paid_up_capital": "",
    "paid_up_capital_in_words": "",

    "adcci_number": "",
    "mohre_establishment_number": "",
    "icp_establishment_number": "",

    "owner_name": "",
    "owner_nationality": "",
    "owner_role": "",
    "share_percentage": "",

    "official_email": "",
    "official_mobile": "",
    "address": "",

    "activity_name": "",
    "activity_code": ""
  }}
}}

Table of Benefits (TOB):
{{
  "document_type": "TOB",
  "data": {{
    "matched_keywords": [],
    "signature_present": false,
    "signature_pages": [],
    "signature_locations": [],
    "signature_status": "declined",
    "validation_status": "declined",
    "decline_reason": ""
  }}
}}

Unknown (when TOB is requested but not identified as TOB):
{{
  "document_type": "Unknown",
  "data": {{
    "matched_keywords": [],
    "signature_present": false,
    "signature_pages": [],
    "signature_locations": [],
    "signature_status": "declined",
    "validation_status": "declined",
    "decline_reason": "Document is not a TOB"
  }}
}}

----------------------------------------
RULES
----------------------------------------

Return JSON only.

If a checkbox clearly indicates No, return "No".
If a checkbox clearly indicates Yes, return "Yes".
Only return "" if the question is missing.

Do not guess missing values.

Passport Number Rules (applies to Passport, UAE Visa, and Labour Contract):
Passport numbers may begin with an alphabetic letter followed by digits.
Example valid formats:
V8333955
K12345678
E9876543

Important:
The first character may be a LETTER. Do not convert letters to numbers.

Common OCR mistakes:
V may look like 1
O may look like 0
I may look like 1

Always preserve the alphabetic character if it appears before the digits.
If the OCR text shows a letter followed by digits, return it exactly as written.

When extracting Passport Number:
Always copy the value exactly from the OCR text.
Do not modify characters.
Do not replace letters with numbers.

----------------------------------------
OCR TEXT
----------------------------------------

{safe_text}

"""
    return prompt


# ---------------------------------------------------------------------------
# Gemini AI API Call
# ---------------------------------------------------------------------------

def call_gemini_ai(prompt: str, file_bytes: bytes = None, mime_type: str = None, retries: int = 2) -> dict:
    """
    Send a prompt to the Google Gemini API and return the parsed JSON.
    Optimized to reuse the client and handle potential throttling.
    """
    client = _get_genai_client()
    if not client:
        print("--- [AI] ERROR: GEMINI_API_KEY is not set in the environment ---")
        return {"error": "GEMINI_API_KEY is not configured. Please set it in your .env file."}

    def log_timing(message):
        try:
            log_file = settings.BASE_DIR / "extraction_performance.log"
            with open(log_file, "a") as f:
                f.write(f"[{datetime.now()}] [AI] {message}\n")
        except:
            pass
        print(f"--- [AI] {message} ---")

    log_timing(f"Sending prompt to Gemini (prompt length: {len(prompt)}, has_file: {file_bytes is not None})")

    # gemini-1.5-flash is used for maximum stability and document accuracy.
    # model_id = "gemini-2.5-pro"
    model_id = "gemini-2.5-flash"

    for attempt in range(retries + 1):
        try:
            attempt_start = datetime.now()
            log_timing(f"Attempt {attempt+1} started using {model_id}...")
            
            # Construct contents: a list of parts (prompt text + optional file)
            contents = [prompt]
            if file_bytes and mime_type:
                contents.append(types.Part.from_bytes(data=file_bytes, mime_type=mime_type))

            response = client.models.generate_content(
                model=model_id,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.0,
                    max_output_tokens=65535,
                ),
            )
            raw_response = response.text
            attempt_end = datetime.now()
            duration = (attempt_end - attempt_start).total_seconds()
            log_timing(f"Raw response received (attempt {attempt+1}, length: {len(raw_response or '')}, duration: {duration:.2f}s)")

            if not raw_response:
                print("--- [AI] Empty response received ---")
                continue

            # Primary parse — response_mime_type=json should give clean JSON
            try:
                result = json.loads(raw_response)
                if isinstance(result, dict):
                    print(f"--- [AI] JSON parsed successfully (keys: {list(result.keys())}) ---")

                    # Fix Visa passport OCR issue
                    if result.get("document_type") in ["UAE Visa", "eVisa", "Residence Visa"]:
                        result["data"] = _fix_visa_passport_number(result.get("data", {}), prompt)

                    if result.get("document_type") == "Medical Application Form":
                        result["data"] = _apply_maf_defaults(result.get("data", {}))

                    # Normalize names for all document types (Given Name first)
                    if "data" in result:
                        result["data"] = _normalize_all_names(result["data"])

                    return result
            except json.JSONDecodeError:
                print("--- [AI] Direct JSON parse failed, attempting cleanup ---")

            # Fallback: strip any accidental markdown fences and repair
            cleaned = _clean_json_response(raw_response)
            if "{" in cleaned:
                try:
                    result = json.loads(cleaned)
                    if isinstance(result, dict):
                        print("--- [AI] JSON parsed after cleanup ---")
                        if result.get("document_type") in ["UAE Visa", "eVisa", "Residence Visa"]:
                            result["data"] = _fix_visa_passport_number(result.get("data", {}), prompt)
                        if result.get("document_type") == "Medical Application Form":
                            result["data"] = _apply_maf_defaults(result.get("data", {}))

                        # Normalize names for all document types (Given Name first)
                        if "data" in result:
                            result["data"] = _normalize_all_names(result["data"])

                        return result
                except json.JSONDecodeError:
                    pass

            # Last resort: anchor-based extraction
            extracted = _extract_json_with_key(raw_response, '"document_type"')
            if extracted:
                try:
                    result = json.loads(extracted)
                    if isinstance(result, dict) and result:
                        print("--- [AI] JSON parsed via anchor extraction ---")
                        if result.get("document_type") in ["UAE Visa", "eVisa", "Residence Visa"]:
                            result["data"] = _fix_visa_passport_number(result.get("data", {}), prompt)
                        if result.get("document_type") == "Medical Application Form":
                            result["data"] = _apply_maf_defaults(result.get("data", {}))

                        # Normalize names for all document types (Given Name first)
                        if "data" in result:
                            result["data"] = _normalize_all_names(result["data"])

                        return result
                except json.JSONDecodeError:
                    pass

            return {"error": f"Gemini returned non-JSON content: {raw_response[:200]}"}

        except Exception as e:
            err_str = str(e)
            
            # Special handling for Model Not Found / 404
            if "404" in err_str or "NOT_FOUND" in err_str:
                print(f"--- [AI] MODEL ERROR (404): {err_str} ---")
                return {"error": f"Model 'gemini-flash-latest' not found or not supported. Error: {err_str[:100]}"}
            
            # Special handling for Quota/Resource Exhausted (429)
            if "ResourceExhausted" in err_str or "429" in err_str:
                quota_msg = "Gemini API Quota Exceeded (429). "
                if "limit: 0" in err_str or "free_tier" in err_str:
                    quota_msg += "Your API key might not have 'Free Tier' enabled or is in an unsupported region. Please check AI Studio."
                else:
                    quota_msg += "Too many requests. Please wait a moment and try again."
                
                print(f"--- [AI] QUOTA ERROR: {quota_msg} ---")
                return {"error": quota_msg}

            # Retry on transient server-side errors
            if attempt < retries and any(code in err_str for code in ["502", "503", "504", "UNAVAILABLE"]):
                print(f"--- [AI] Transient error on attempt {attempt+1}: {err_str}. Retrying in 2s... ---")
                time.sleep(2)
                continue

            print(f"--- [AI] Gemini request error: {e} ---")
            import traceback
            traceback.print_exc()
            return {"error": f"Gemini request failed: {err_str}"}

    return {"error": "Gemini request failed after multiple retries"}

# def _apply_maf_defaults(data: dict) -> dict:
#     """
#     Post-processing for Medical Application Forms.
#     Ensures that medical questionnaire fields are never empty where a default is safe.
#     Defaults standard medical conditions to 'No' if missing. For 'good_health', we prioritize AI extraction.
#     """
#     if not isinstance(data, dict):
#         return data

#     # Fields that should default to 'No'
#     no_defaults = [
#         "insurance_substandard_terms", "insurance_declined", "hazardous_sports",
#         "infectious_diseases", "cancer", "endocrine_diseases", "blood_disorders",
#         "mental_disorders", "nervous_system", "cardiovascular", "respiratory",
#         "digestive_system", "genitourinary", "maternity_history", "musculoskeletal",
#         "congenital", "perinatal", "injury_poisoning", "previous_hospitalization",
#         "chronic_disease", "pre_existing_disease", "organ_surgery", "weight_change",
#         "smoking_alcohol", "bone_fractures", "Shortness_vision", "Hepatitis", "dental_problems", "pregnant", "pregnancy_complications",
#         "trying_to_conceive", "fertility_treatment", "has_cancer", "family_cancer_history"
#     ]

#     for field in no_defaults:
#         val = str(data.get(field, "")).strip().lower()
#         if "yes" in val:
#             data[field] = "Yes"
#         elif "no" in val:
#             data[field] = "No"
#         else:
#             # Preserve AI output (e.g., empty string for unreliability)
#             # DO NOT default to 'No' if missing or 'none/null'.
#             data[field] = "" if val in ["", "none", "null", "n/a"] else data.get(field)

#     # Final logical check: If details exist, the checkbox MUST be Yes
#     # This prevents AI from missing a tick when the user has clearly filled in details.
#     logic_mapping = {
#         "dental_problems": "dental_details",
#         "has_cancer": ["cancer_status", "cancer_diagnosis", "cancer_surgery", "cancer_medication"],
#         "cancer": ["cancer_status", "cancer_diagnosis", "cancer_surgery", "cancer_medication"],
#         "hazardous_sports": "hazardous_sports_details",
#         # REMOVED: "pregnant": "last_menstrual_period" (LMP is collected for all women, not just pregnant ones)
#     }

#     for checkbox_field, detail_fields in logic_mapping.items():
#         if isinstance(detail_fields, str):
#             detail_fields = [detail_fields]
        
#         has_details = False
#         for df in detail_fields:
#             val = str(data.get(df, "")).strip().lower()
#             if val and val not in ["", "none", "null", "n/a", "-", "no"]:
#                 has_details = True
#                 break
        
#         if has_details:
#             data[checkbox_field] = "Yes"

#     # Specific logic for good_health
#     gh_val = str(data.get("good_health", "")).strip().lower()
#     if "no" in gh_val:
#         data["good_health"] = "No"
#     elif "yes" in gh_val:
#         data["good_health"] = "Yes"
#     else:
#         # If the AI is completely unsure or returned nothing, 
#         # we do NOT default to 'No' for this field to avoid false negatives.
#         # We preserve what the AI returned (which might be empty string).
#         pass


#     return data

def _normalize_yes_no(value):
    """
    Normalize checkbox values safely.

    Only explicit Yes/No values are converted.
    Any unrelated content (dates, names, numbers, punctuation) returns "".
    """
    if value is None:
        return ""

    val = str(value).strip()
    if not val:
        return ""

    lower = val.lower()

    # Empty-like values
    if lower in {"", "none", "null", "n/a", "-", "--"}:
        return ""

    # Explicit No values
    if lower in {
        "no", "n", "false", "unchecked",
        "not checked", "unselected"
    }:
        return "No"

    # Explicit Yes values
    if lower in {
        "yes", "y", "true", "checked",
        "selected", "✓", "✔", "☑", "☒",
        "x", "✗", "✘"
    }:
        return "Yes"

    # Safe partial matches
    if re.fullmatch(r"\s*(yes)\s*", lower):
        return "Yes"

    if re.fullmatch(r"\s*(no)\s*", lower):
        return "No"

    # Do NOT guess based on punctuation.
    return ""


def _apply_maf_defaults(data: dict) -> dict:
    if not isinstance(data, dict):
        return data

    yes_no_fields = [
        "insurance_substandard_terms",
        "insurance_declined",
        "hazardous_sports",
        "infectious_diseases",
        "cancer",
        "endocrine_diseases",
        "blood_disorders",
        "mental_disorders",
        "nervous_system",
        "cardiovascular",
        "respiratory",
        "digestive_system",
        "genitourinary",
        "maternity_history",
        "musculoskeletal",
        "congenital",
        "perinatal",
        "injury_poisoning",
        "previous_hospitalization",
        "chronic_disease",
        "pre_existing_disease",
        "organ_surgery",
        "good_health",
        "weight_change",
        "smoking_alcohol",
        "bone_fractures",
        "Shortness_vision",
        "Hepatitis",
        "dental_problems",
        "pregnant",
        "pregnancy_complications",
        "trying_to_conceive",
        "fertility_treatment",
        "has_cancer",
        "family_cancer_history",
        "uae_resident",
        "already_insured"
    ]

    # Ensure all expected fields exist
    for field in yes_no_fields:
        if field not in data:
            data[field] = ""

    # Normalize all Yes/No fields
    for field in yes_no_fields:
        data[field] = _normalize_yes_no(data.get(field))

    # Logical inference from detail fields
    logic_mapping = {
        "dental_problems": ["dental_details"],
        "has_cancer": [
            "cancer_status",
            "cancer_diagnosis",
            "cancer_surgery",
            "cancer_medication"
        ],
        "cancer": [
            "cancer_status",
            "cancer_diagnosis",
            "cancer_surgery",
            "cancer_medication"
        ],
        "hazardous_sports": ["hazardous_sports_details"],
    }

    for checkbox_field, detail_fields in logic_mapping.items():
        has_details = False

        for detail_field in detail_fields:
            value = str(data.get(detail_field, "")).strip().lower()
            if value and value not in ["", "none", "null", "n/a", "-", "no"]:
                has_details = True
                break

        if has_details:
            data[checkbox_field] = "Yes"

    return data


def _normalize_all_names(data: dict) -> dict:
    """
    Ensures that all name fields follow the Given Name first order.
    If a name contains a comma (e.g. "SMITH, JOHN"), it flips it to "JOHN SMITH".
    """
    if not isinstance(data, dict):
        return data

    name_fields = ["full_name", "name", "employee_name", "insured_name", "policy_holder_name"]
    
    for field in name_fields:
        if field in data and data[field]:
            val = str(data[field]).strip()
            # If name is in "SURNAME, GIVEN NAME" format
            if "," in val:
                parts = [p.strip() for p in val.split(",")]
                if len(parts) == 2:
                    # Flip: Surname, Given -> Given Surname
                    new_val = f"{parts[1]} {parts[0]}"
                    print(f"--- [AI] Normalized {field} from '{val}' to '{new_val}' ---")
                    data[field] = new_val
            
            # Clean up double spaces
            if data[field]:
                data[field] = " ".join(str(data[field]).split())

    return data


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------

# All Labour Contract field keys in the order we expect them
_LABOUR_FIELDS = [
    "establishment_name", "establishment_number", "employer_representative",
    "emirate", "employer_email", "employer_phone", "work_style",
    "transaction_number", "contract_type", "contract_issue_date",
    "employee_name", "employee_nationality", "employee_dob",
    "employee_passport_no", "employee_qualification", "employee_phone",
    "job_title", "work_hours", "weekly_rest", "annual_leave",
    "contract_start_date", "contract_end_date", "approval_date",
    "total_salary",
]

_PASSPORT_FIELDS = ["passport_number", "full_name", "nationality", "date_of_birth", "issuing_date", "expiry_date", "stamp_date", "from_date", "to_date", "transaction_date", "transaction_type", "port_name"]
_EMIRATES_ID_FIELDS = ["emirates_id", "name", "nationality", "dob", "expiry_date", "issuing_date", "family_sponsor_name", "gender", "occupation", "employer", "issuing_place", "card_type"]
_VISA_FIELDS = ["emirates_id", "permit_number", "file_number", "uid_no", "passport_no", "name", "nationality", "profession", "issuing_date", "expiry_date", "sponsor_name", "employer", "stamp_date", "from_date", "to_date", "transaction_date", "transaction_type", "port_name"]
_TRAVEL_HISTORY_FIELDS = ["passport_no", "name", "from_date", "to_date", "transaction_date", "transaction_type", "port_name"]
_COC_FIELDS = ["insured_name", "policy_number", "policy_expiry_date", "inception_date", "insured_until", "coc_reference_no", "coc_validity_date", "issue_date", "insurer_name"]
_RESIDENCE_CANCELLATION_FIELDS = ["uid_no", "emirates_id", "residence_no", "passport_no", "full_name", "profession", "employer", "place_of_issue", "cancel_date"]

_MAF_FIELDS = [
    "insured_name", "application_date", "required_plan", "application_policy_no",
    "current_address", "active_at_work_since", "nationality", "gender", "date_of_birth",
    "marital_status", "height_cm", "weight_kg", "uae_resident", "already_insured",
    "insured_since", "insurance_substandard_terms", "insurance_declined",
    "hazardous_sports", "hazardous_sports_details", "infectious_diseases",
    "cancer", "endocrine_diseases", "blood_disorders", "mental_disorders",
    "nervous_system", "cardiovascular", "respiratory", "digestive_system",
    "genitourinary", "maternity_history", "musculoskeletal", "congenital",
    "perinatal", "injury_poisoning", "previous_hospitalization", "chronic_disease",
    "pre_existing_disease", "organ_surgery", "good_health", "weight_change",
    "smoking_alcohol", "bone_fractures", "Shortness_vision", "Hepatitis",
    "dental_problems", "dental_details", "dental_last_treatment",
    "pregnant", "pregnancy_complications", "last_menstrual_period", "trying_to_conceive",
    "fertility_treatment", "has_cancer", "cancer_status", "cancer_diagnosis",
    "cancer_surgery", "cancer_chemotherapy_cycles", "cancer_radiotherapy_cycles",
    "cancer_radiation_cycles", "cancer_medication", "family_cancer_history"
]

_TOB_FIELDS = ["matched_keywords", "signature_present", "signature_pages", "signature_locations", "signature_status", "validation_status", "decline_reason"]

_DOC_TYPE_FIELDS = {
    "Labour Contract": _LABOUR_FIELDS,
    "Passport": _PASSPORT_FIELDS,
    "Emirates ID": _EMIRATES_ID_FIELDS,
    "UAE Visa": _VISA_FIELDS,
    "eVisa": _VISA_FIELDS,
    "Residence Visa": _VISA_FIELDS,
    "Medical Application Form": _MAF_FIELDS,
    "COC": _COC_FIELDS,
    "Residence Cancellation": _RESIDENCE_CANCELLATION_FIELDS,
    "Travel History": _TRAVEL_HISTORY_FIELDS,
    "TOB": _TOB_FIELDS,
    "Unknown": _TOB_FIELDS
}

def _parse_reasoning_key_values(reasoning: str) -> dict:
    """
    Last-resort extractor: the reasoning model writes every field as
        field_name: "value"
    in its chain-of-thought even when it never produces JSON in content.
    This function detects the document type from keywords in the reasoning
    text, then regex-extracts all matching key:value pairs.

    Returns a properly shaped {"document_type": ..., "data": {...}} dict,
    or {} if nothing useful could be extracted.
    """
    # --- Detect document type from reasoning text ---
    lower = reasoning.lower()
    if any(k in lower for k in ["labour contract", "labor contract", "employment contract", "mohre", "establishment_name"]):
        doc_type = "Labour Contract"
    elif any(k in lower for k in ["passport", "passport_number"]):
        doc_type = "Passport"
    elif any(k in lower for k in ["emirates id", "emirates_id", "identity card"]):
        doc_type = "Emirates ID"
    elif any(k in lower for k in ["residence", "entry permit", "uae visa", "uid_no", "file number", "evisa"]):
        if "evisa" in lower:
            doc_type = "eVisa"
        elif "file number" in lower:
            doc_type = "Residence Visa"
        else:
            doc_type = "UAE Visa"
    elif any(k in lower for k in ["continuity certificate", "certificate of continuity", "coc reference", "doh coc", "dubai insurance", "health insurance certificate"]):
        doc_type = "COC"
    elif any(k in lower for k in ["residence cancellation", "cancel date"]):
        doc_type = "Residence Cancellation"
    elif any(k in lower for k in ["table of benefits", "tob", "schedule of benefits", "essential benefit plan"]):
        doc_type = "TOB"
    else:
        print("--- [AI] KV-parse: cannot detect document type from reasoning ---")
        return {}

    print(f"--- [AI] KV-parse: detected document type '{doc_type}' from reasoning keywords ---")
    fields = _DOC_TYPE_FIELDS[doc_type]

    # --- Regex: field_name: "value" or field_name: value ---
    data = {}
    for field in fields:
        # Match:  field_name: "Some Value"  OR  field_name: Some Value (up to newline)
        pattern = rf'{re.escape(field)}\s*:\s*"([^"]*)"|{re.escape(field)}\s*:\s*([^\n"{{}}]+)'
        match = re.search(pattern, reasoning, re.IGNORECASE)
        if match:
            value = (match.group(1) or match.group(2) or "").strip().rstrip(',')
            data[field] = value
        else:
            data[field] = ""

    if not any(data.values()):
        print("--- [AI] KV-parse: no field values found ---")
        return {}

    return {"document_type": doc_type, "data": data}


def _extract_json_with_key(text: str, anchor_key: str = '"document_type"') -> str:
    """
    Search backwards through `text` for the last occurrence of `anchor_key`
    (e.g. '"document_type"'), then walk backwards to find the enclosing '{',
    and forward counting brace depth to find the matching '}'.

    This is far more reliable than a generic first-to-last brace scan when
    the text is a chain-of-thought blob containing many stray brace pairs.

    Returns the extracted JSON string, or "" if the anchor is not found.
    """
    if not text or anchor_key not in text:
        return ""

    # Find the LAST occurrence of the anchor key (model puts answer at end)
    anchor_pos = text.rfind(anchor_key)
    if anchor_pos == -1:
        return ""

    # Walk backwards from anchor_pos to find the opening '{'
    brace_start = text.rfind('{', 0, anchor_pos)
    if brace_start == -1:
        return ""

    # Walk forward from brace_start counting depth to find the matching '}'
    depth = 0
    i = brace_start
    while i < len(text):
        ch = text[i]
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return text[brace_start:i + 1]
        i += 1

    # Closing brace never matched — return what we have and hope for the best
    print("--- [AI] WARNING: Unmatched brace in anchor extraction, returning partial ---")
    return text[brace_start:]

def _clean_json_response(text: str) -> str:
    """
    More aggressive JSON extractor and repairer.
    Strip any markdown code fences, trim whitespace, and attempt to 
    repair missing closing braces if the JSON appears truncated.
    """
    if not text:
        return "{}"
        
    text = text.strip()

    # Remove markdown json fences
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r'\s*```$', '', text, flags=re.MULTILINE)

    # Find the FIRST opening brace
    brace_start = text.find('{')
    if brace_start == -1:
        return "{}"

    # Find the LAST closing brace
    brace_end = text.rfind('}')

    # If closing brace is missing or appears before start (very rare), 
    # it might be truncated.
    if brace_end == -1 or brace_end < brace_start:
        print("--- [AI] WARNING: Closing brace missing. Attempting simple repair... ---")
        # Count open braces and add missing closers
        open_count = text.count('{')
        close_count = text.count('}')
        missing = open_count - close_count
        if missing > 0:
            text += ('}' * missing)
            brace_end = len(text) - 1
            print(f"--- [AI] Repaired JSON by adding {missing} braces ---")
        else:
            # Maybe it ended at a comma or mid-key? 
            # This is hard to repair reliably, but let's try adding one brace.
            text += '}'
            brace_end = len(text) - 1

    if brace_start != -1 and brace_end != -1:
        text = text[brace_start:brace_end + 1]

    return text.strip()


def _fix_visa_passport_number(data: dict, ocr_text: str) -> dict:
    """
    Fix cases where the passport number loses its leading letter
    (e.g. 'V8333955' becomes '18333955').
    """

    passport = data.get("passport_no", "")

    if not passport:
        return data

    # If passport is digits only, try to recover letter from OCR
    if passport.isdigit():

        # search pattern: letter + digits
        match = re.search(r'\b([A-Z][0-9]{7,8})\b', ocr_text)

        if match:
            candidate = match.group(1)

            if candidate[1:] == passport[-7:] or candidate[1:] == passport:
                data["passport_no"] = candidate
                print(f"--- [AI] Corrected passport number to {candidate} ---")

    return data