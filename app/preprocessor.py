import re
from typing import Dict, Any
from .models import CaseInput

class Preprocessor:
    def process(self, case: CaseInput) -> Dict[str, Any]:
        """
        Parses the raw message into headers and body.
        Preserves the original message.
        """
        raw = case.raw_message
        headers = {}
        body = raw

        if "\n\n" in raw:
            header_part, body_part = raw.split("\n\n", 1)
            # Try to parse headers if they look like typical email headers
            is_email = False
            for line in header_part.split("\n"):
                if re.match(r"^[A-Za-z\-]+:\s", line):
                    is_email = True
                    break
            
            if is_email:
                for line in header_part.split("\n"):
                    if ":" in line:
                        key, val = line.split(":", 1)
                        headers[key.strip().lower()] = val.strip()
                body = body_part

        return {
            "case_id": case.case_id,
            "raw_message": raw,
            "headers": headers,
            "body": body
        }
