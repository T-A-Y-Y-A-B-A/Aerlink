from typing import Dict, Any, List
from .models import CaseFacts, Decision, Action, RebookAction, CompensationAction, HotelAction, RefundAction

class SafetyGate:
    def __init__(self, ops_client):
        self.ops = ops_client

    def validate(self, facts: CaseFacts, decision: Decision) -> bool:
        if decision.escalate:
            return True # Escalation is always safe

        if not facts.booking_verified:
            return False

        if facts.intent and facts.intent.is_prompt_injection:
            return False

        if facts.identity_ambiguous:
            return False
            
        history = self.ops.get_customer_history("TODO_CUSTOMER_ID") if False else {} # Simplified
        
        for action in decision.actions:
            if isinstance(action, CompensationAction):
                if not facts.entitlement:
                    return False
                if action.amount > facts.entitlement.compensation_amount:
                    return False # Prevent paying more than entitled
                
            if isinstance(action, HotelAction):
                if not facts.entitlement or not facts.entitlement.hotel_allowed:
                    return False
                    
        return True
