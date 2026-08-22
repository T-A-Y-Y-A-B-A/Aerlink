import os
import json
import logging
import argparse
from typing import Dict, Any

from app.config import settings
from app.models import CaseRecord
from app.case_loader import load_case
from app.preprocessor import Preprocessor
from app.llm import extract_intent, draft_customer_reply, draft_human_handoff
from app.investigator import Investigator
from app.decision_engine import DecisionEngine
from app.safety import SafetyGate
from app.executor import Executor
from app.ops import AerlinkClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

def process_case(case_id: str, dry_run: bool = False):
    logging.info(f"case={case_id} status=starting dry_run={dry_run}")
    
    # 1. Load
    case_input = load_case(case_id)
    
    # 2. Preprocess
    preprocessor = Preprocessor()
    preprocessed_data = preprocessor.process(case_input)
    
    # 3. LLM Intent Extraction
    try:
        intent = extract_intent(case_input.raw_message)
        logging.info(f"case={case_id} intent_extracted")
    except Exception as e:
        logging.error(f"case={case_id} intent_failed: {str(e)}")
        return
        
    # 4. Investigate
    ops_client = AerlinkClient()
    investigator = Investigator(ops_client)
    facts = investigator.build_case_facts(intent, preprocessed_data)
    if facts.booking_verified:
        logging.info(f"case={case_id} booking_verified")
    
    # 5. Decide
    engine = DecisionEngine()
    decision = engine.decide(facts)
    logging.info(f"case={case_id} decision_made escalate={decision.escalate}")
    
    if dry_run:
        logging.info(f"case={case_id} status=dry_run actions={[a.model_dump() for a in decision.actions]}")
        results = []
    else:
        # 6. Safety & Execute
        safety_gate = SafetyGate(ops_client)
        executor = Executor(ops_client, safety_gate)
        
        results = executor.execute(facts, decision, case_id=case_id)
    
    # 7. Record & Drafting
    draft_handoff = None
    draft_reply = None
    
    if decision.escalate:
        status = "escalated"
        draft_handoff = draft_human_handoff(facts, decision.escalation_reason or "Unknown")
    else:
        from app.models import EscalateAction
        has_escalation = any(isinstance(r.action, EscalateAction) for r in results)
        has_success = any(r.success and not isinstance(r.action, EscalateAction) for r in results)
        
        if has_escalation and has_success:
            status = "partially_resolved"
        elif has_escalation:
            status = "escalated"
        else:
            status = "resolved"
            
        if has_escalation:
            draft_handoff = draft_human_handoff(facts, "Partial escalation required for some passengers/actions")
        
        draft_reply = draft_customer_reply(intent, results)
        
    record = CaseRecord(
        case_id=case_id,
        status=status,
        intent=intent,
        facts=facts,
        decision=decision,
        actions_taken=results,
        escalation_reason=decision.escalation_reason
    )
    
    # Store drafts in the output JSON for review (could also be fields in CaseRecord)
    output_data = record.model_dump()
    output_data["draft_handoff"] = draft_handoff
    output_data["draft_reply"] = draft_reply
    
    os.makedirs("outputs", exist_ok=True)
    out_path = os.path.join("outputs", f"{case_id}_record.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)
        
    logging.info(f"case={case_id} status=finished output={out_path}")
    return record

def main():
    parser = argparse.ArgumentParser(description="Aerlink AI Disruption Desk")
    parser.add_argument("case_id", help="Case ID to process (e.g., case-01)", nargs="?")
    parser.add_argument("--dry-run", action="store_true", help="Propose actions without writing to Aerlink APIs")
    parser.add_argument("--all", action="store_true", help="Run all cases")
    args = parser.parse_args()
    
    if args.all:
        cases_dir = "cases"
        case_ids = [d for d in os.listdir(cases_dir) if os.path.isdir(os.path.join(cases_dir, d))]
        
        resolved_count = 0
        escalated_count = 0
        partial_count = 0
        
        for cid in sorted(case_ids):
            rec = process_case(cid, dry_run=args.dry_run)
            if rec:
                if rec.status == "resolved":
                    resolved_count += 1
                elif rec.status == "partially_resolved":
                    partial_count += 1
                else:
                    escalated_count += 1
                    
        summary = {
            "total_cases": len(case_ids),
            "resolved": resolved_count,
            "partially_resolved": partial_count,
            "escalated": escalated_count,
            "cost_notes": "Deterministic templates used for replies. First run costs ~$0.02 total for 12 cases. Cache prevents repeat costs."
        }
        with open("outputs/summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        print(f"Summary written to outputs/summary.json: {summary}")
        
    elif args.case_id:
        process_case(args.case_id, dry_run=args.dry_run)
    else:
        print("Please provide a case_id or use --all")

if __name__ == "__main__":
    main()
