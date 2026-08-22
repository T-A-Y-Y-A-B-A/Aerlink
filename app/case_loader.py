import os
from .models import CaseInput

def load_case(case_id: str, cases_dir: str = "cases") -> CaseInput:
    """
    Loads a case from the given directory.
    Its only responsibility: "Give the system the case."
    """
    case_path = os.path.join(cases_dir, case_id)
    inbound_path = os.path.join(case_path, "inbound.txt")
    
    if not os.path.exists(inbound_path):
        raise FileNotFoundError(f"Case file not found: {inbound_path}")
        
    with open(inbound_path, "r", encoding="utf-8") as f:
        raw_message = f.read()
        
    return CaseInput(case_id=case_id, raw_message=raw_message)
