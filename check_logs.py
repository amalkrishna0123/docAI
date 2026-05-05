import os
import django
from pathlib import Path

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medical_insurance.settings')
django.setup()

from django.conf import settings

base_dir = settings.BASE_DIR
log_file = base_dir / "extraction_performance.log"

print(f"BASE_DIR: {base_dir}")
print(f"Log file path: {log_file}")
print(f"Log file exists: {log_file.exists()}")
if log_file.exists():
    print(f"Log file size: {log_file.stat().st_size} bytes")
    with open(log_file, "r") as f:
        print("--- CONTENT ---")
        print(f.read())
        print("---------------")
