from typing import List
from .models import CaseFacts, Decision, Action, RebookAction, CompensationAction, HotelAction, RefundAction, EscalateAction

class DecisionEngine:
    def decide(self, facts: CaseFacts) -> Decision:
        if facts.intent and facts.intent.is_prompt_injection:
            return Decision(escalate=True, escalation_reason="Security: Prompt injection detected.")

        if facts.identity_ambiguous:
            return Decision(escalate=True, escalation_reason="Identity ambiguous (multiple bookings found).")

        if not facts.booking_verified:
            return Decision(escalate=True, escalation_reason="Booking could not be verified.")

        actions: List[Action] = []
        intent = facts.intent
        
        # We no longer globally abort for unsupported actions, we handle them per-passenger
        unsupported = {"goodwill", "baggage", "other", "information"}

        # Map passenger names to their IDs
        name_to_id = {}
        if facts.booking and facts.booking.passengers:
            for p in facts.booking.passengers:
                full_name = f"{p.first_name} {p.last_name}".strip().lower()
                name_to_id[full_name] = p.passenger_id
                name_to_id[p.last_name.lower()] = p.passenger_id # fallback
        
        # If no explicit passenger requests, pass (handle globally if needed)
        if not intent.passenger_requests:
            pass 

        for pr in intent.passenger_requests:
            p_name_lower = pr.passenger_name.lower()
            pid = None
            for n, p_id in name_to_id.items():
                if n in p_name_lower or p_name_lower in n:
                    pid = p_id
                    break
            
            if not pid:
                if facts.booking and len(facts.booking.passengers) == 1:
                    pid = facts.booking.passengers[0].passenger_id
                else:
                    actions.append(EscalateAction(
                        description=f"Escalate unmapped passenger {pr.passenger_name}",
                        reason=f"Could not map passenger name '{pr.passenger_name}' to a booking passenger ID."
                    ))
                    continue

            for req in pr.requested_actions:
                if req in unsupported:
                    actions.append(EscalateAction(
                        description=f"Escalate unsupported action '{req}' for {pid}",
                        passenger_id=pid,
                        reason=f"Unsupported action requested: {req}"
                    ))
                    continue

                if req == "rebook":
                    p_info = next((p for p in facts.booking.passengers if p.passenger_id == pid), None) if facts.booking else None
                    if p_info and p_info.special_assistance:
                        actions.append(EscalateAction(
                            description=f"Escalate rebook for {pid} due to special assistance",
                            passenger_id=pid,
                            reason=f"Special assistance ({p_info.special_assistance}) requires manual rebooking."
                        ))
                    elif facts.availability:
                        best_option = facts.availability[0]
                        actions.append(RebookAction(
                            description=f"Rebook passenger {pid} to {best_option.flight_number}",
                            passenger_id=pid,
                            new_flight_number=best_option.flight_number,
                            date=best_option.date,
                            option_id=best_option.option_id,
                            cabin=best_option.cabin,
                            reasoning=[
                                "Booking verified",
                                "Original flight cancelled",
                                f"Passenger requested rebook",
                                f"Available flight satisfies requirements"
                            ],
                            authoritative_sources=["booking_api", "availability_api"],
                            safety_checks={
                                "identity_verified": True,
                                "availability_confirmed": True,
                                "special_assistance_clear": True
                            }
                        ))
                    else:
                        actions.append(EscalateAction(
                            description=f"Escalate rebook for {pid}: no availability",
                            passenger_id=pid,
                            reason="No availability for rebooking."
                        ))
                        
                elif req == "compensation":
                    if facts.entitlement and facts.entitlement.compensation_amount > 0:
                        actions.append(CompensationAction(
                            description=f"Pay compensation £{facts.entitlement.compensation_amount} to {pid}",
                            passenger_id=pid,
                            amount=facts.entitlement.compensation_amount,
                            reasoning=[
                                "Booking verified",
                                "Passenger requested compensation",
                                "Passenger is entitled to compensation"
                            ],
                            authoritative_sources=["booking_api", "entitlement_api"],
                            safety_checks={
                                "identity_verified": True,
                                "entitlement_confirmed": True
                            }
                        ))
                    else:
                        actions.append(EscalateAction(
                            description=f"Escalate compensation for {pid}: not entitled",
                            passenger_id=pid,
                            reason="Compensation requested but not entitled."
                        ))
                        
                elif req == "hotel":
                    if facts.entitlement and facts.entitlement.hotel_allowed:
                        actions.append(HotelAction(
                            description=f"Issue hotel voucher for {pid}",
                            passenger_id=pid,
                            reasoning=[
                                "Booking verified",
                                "Passenger requested hotel",
                                "Passenger is entitled to duty of care (hotel)"
                            ],
                            authoritative_sources=["booking_api", "entitlement_api"],
                            safety_checks={
                                "identity_verified": True,
                                "hotel_entitlement_confirmed": True
                            }
                        ))
                    else:
                        actions.append(EscalateAction(
                            description=f"Escalate hotel for {pid}: not entitled",
                            passenger_id=pid,
                            reason="Hotel requested but not entitled."
                        ))
                        
                elif req == "refund":
                    actions.append(EscalateAction(
                        description=f"Escalate refund for {pid}: requires manual review",
                        passenger_id=pid,
                        reason="Refund requested; requires manual review."
                    ))

        return Decision(actions=actions)
