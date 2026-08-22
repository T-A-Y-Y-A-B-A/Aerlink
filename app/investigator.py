from typing import Dict, Any, List
from .models import CaseFacts, PassengerIntent, Booking, Passenger, Flight, Entitlement, AvailabilityOption
from .ops import AerlinkClient

class Investigator:
    def __init__(self, ops_client: AerlinkClient):
        self.ops = ops_client

    def build_case_facts(self, intent: PassengerIntent, preprocessed: Dict[str, Any]) -> CaseFacts:
        facts = CaseFacts(intent=intent)
        
        # 1. Booking identification
        booking_ref = None
        if intent.booking_references:
            booking_ref = intent.booking_references[0]
        else:
            # Fallback to search if we have a passenger name
            search_query = None
            if intent.passenger_requests:
                search_query = intent.passenger_requests[0].passenger_name
            elif "from" in preprocessed.get("headers", {}):
                search_query = preprocessed["headers"]["from"]
            
            if search_query:
                results = self.ops.search_booking(search_query)
                if results.get("match_count", 0) == 1:
                    booking_ref = results["results"][0]["booking_ref"]
                elif results.get("match_count", 0) > 1:
                    facts.identity_ambiguous = True
        
        if not booking_ref:
            return facts

        # 2. Booking retrieval
        try:
            booking_data = self.ops.get_booking(booking_ref)
            
            passengers = []
            for p_data in booking_data.get("passengers", []):
                name_parts = p_data.get("names", "").split(" ", 1)
                first_name = name_parts[0] if len(name_parts) > 0 else ""
                last_name = name_parts[1] if len(name_parts) > 1 else ""
                passengers.append(Passenger(
                    passenger_id=p_data.get("passenger_id"),
                    first_name=first_name,
                    last_name=last_name,
                    special_assistance=p_data.get("assistance")
                ))
            
            flights = []
            for s_data in booking_data.get("segments", []):
                flights.append(s_data.get("flight_no"))
                if s_data.get("is_affected"):
                    facts.needs_rebooking = True
                
            facts.booking = Booking(
                booking_reference=booking_ref,
                passengers=passengers,
                flights=flights,
                status=booking_data.get("disruption")
            )
            facts.booking_verified = True
        except Exception as e:
            return facts

        # 3. Entitlement
        try:
            entitlement_data = self.ops.calculate_entitlement(booking_ref)
            comp_gbp = entitlement_data.get("compensation", {}).get("amount_gbp", 0.0)
            
            # Simplified for now: just map basic flags
            duty_of_care = entitlement_data.get("duty_of_care", {})
            entitlements = duty_of_care.get("entitlements", [])
            
            hotel_allowed = "HOTEL_ACCOMMODATION" in entitlements
            
            facts.entitlement = Entitlement(
                compensation_amount=comp_gbp,
                hotel_allowed=hotel_allowed,
                rebooking_allowed=True,
                refund_allowed=True
            )
        except Exception as e:
            pass
            
        # 4. Flight Retrieval & Availability (if rebooking requested/needed)
        any_rebook_requested = any("rebook" in pr.requested_actions for pr in intent.passenger_requests)
        if any_rebook_requested or facts.needs_rebooking:
            try:
                for s_data in booking_data.get("segments", []):
                    origin = s_data.get("origin")
                    dest = intent.destination or s_data.get("destination")
                    date = intent.preferred_date or s_data.get("date")
                    
                    if origin and dest and date:
                        try:
                            avail_data = self.ops.search_availability(origin, dest, date)
                            for r in avail_data.get("results", []):
                                if r.get("seats_available", 0) > 0:
                                    facts.availability.append(AvailabilityOption(
                                        option_id=r.get("option_id", ""),
                                        flight_number=r.get("flight_no"),
                                        departure_time=r.get("departure_local"),
                                        available_seats=r.get("seats_available"),
                                        date=r.get("date", date),
                                        cabin=r.get("cabin", "ECONOMY")
                                    ))
                        except Exception as e: # Catch 503 if it still fails after retry
                            pass
            except Exception as e:
                pass

        return facts
