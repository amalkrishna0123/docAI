from pathlib import Path
from datetime import datetime
import os

try:
    log_file = Path(r"c:\Projects\Document_Test_Document_AI\test\write_test.log")
    with open(log_file, "a") as f:
        f.write(f"[{datetime.now()}] Write test success\n")
    print(f"Successfully wrote to {log_file}")
except Exception as e:
    print(f"Failed to write: {e}")
