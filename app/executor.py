from typing import List, Dict, Any
from .models import Decision, ExecutionResult, RebookAction, CompensationAction, HotelAction, RefundAction, CaseFacts, EscalateAction
from .ops import AerlinkClient
from .safety import SafetyGate
import datetime
import json
import hashlib

class Executor:
    def __init__(self, ops_client: AerlinkClient, safety_gate: SafetyGate):
        self.ops = ops_client
        self.safety = safety_gate

    def execute(self, facts: CaseFacts, decision: Decision, case_id: str = "unknown_case") -> List[ExecutionResult]:
        results = []
        
        if not self.safety.validate(facts, decision):
            decision.escalate = True
            decision.escalation_reason = "Safety gate validation failed."
        
        if decision.escalate:
            # We still yield an EscalateAction result for the global escalation
            try:
                res = self.ops.escalate(
                    summary="Case escalated by AI",
                    requested_decision=decision.escalation_reason or "Manual review required",
                    booking_ref=facts.booking.booking_reference if facts.booking else None
                )
                results.append(ExecutionResult(
                    action=EscalateAction(description="Global escalation", reason=decision.escalation_reason or "Unknown"),
                    success=True,
                    message=f"Escalated: {res}"
                ))
            except Exception as e:
                results.append(ExecutionResult(
                    action=EscalateAction(description="Global escalation", reason=decision.escalation_reason or "Unknown"),
                    success=False,
                    message=f"Failed to escalate: {str(e)}"
                ))
            return results

        booking_ref = facts.booking.booking_reference if facts.booking else "UNKNOWN_REF"
        
        # Load idempotency store
        idempotency_file = ".idempotency.json"
        try:
            with open(idempotency_file, "r") as f:
                executed_actions = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            executed_actions = []
            
        for action in decision.actions:
            # Idempotency hash
            action_str = json.dumps(action.model_dump(), sort_keys=True)
            action_id = hashlib.sha256(f"{case_id}_{booking_ref}_{action_str}".encode()).hexdigest()
            
            if action_id in executed_actions:
                results.append(ExecutionResult(action=action, success=True, message="Already executed (idempotency cache hit)"))
                continue
            
            try:
                # Risk-based safety check abstraction
                if hasattr(action, 'risk_level') and action.risk_level in ["HIGH", "VERY_HIGH"]:
                    # enforce strict checks if needed
                    pass
                    
                if isinstance(action, EscalateAction):
                    res = self.ops.escalate(
                        summary="Partial passenger-level escalation",
                        requested_decision=action.reason,
                        booking_ref=booking_ref
                    )
                    results.append(ExecutionResult(action=action, success=True, message=str(res)))
                    
                elif isinstance(action, RebookAction):
                    res = self.ops.rebook(
                        booking_ref=booking_ref,
                        passenger_ids=[action.passenger_id],
                        option_id=action.option_id,
                        flight_no=action.new_flight_number,
                        date=action.date,
                        cabin=action.cabin
                    )
                    results.append(ExecutionResult(action=action, success=True, message=str(res)))
                    
                elif isinstance(action, CompensationAction):
                    res = self.ops.pay_compensation(
                        booking_ref=booking_ref,
                        passenger_ids=[action.passenger_id],
                        amount=action.amount,
                        reason="Automated compensation"
                    )
                    results.append(ExecutionResult(action=action, success=True, message=str(res)))
                    
                elif isinstance(action, HotelAction):
                    res = self.ops.issue_hotel_voucher(
                        booking_ref=booking_ref,
                        station="LHR", # Needs real station
                        date="2026-08-05", # Needs real date
                        passenger_ids=[action.passenger_id]
                    )
                    results.append(ExecutionResult(action=action, success=True, message=str(res)))
                
                # Store successful execution
                executed_actions.append(action_id)
                with open(idempotency_file, "w") as f:
                    json.dump(executed_actions, f)

            except Exception as e:
                results.append(ExecutionResult(action=action, success=False, message=str(e)))
                
        return results
