import httpx
from typing import Dict, Any, Optional, List
from .config import settings

class AerlinkClient:
    def __init__(self):
        self.base_url = settings.ops_base_url
        self.headers = {"X-Ops-Key": settings.ops_api_key}

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        response = httpx.get(f"{self.base_url}{path}", headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()

    def _post(self, path: str, json_data: Dict[str, Any]) -> Dict[str, Any]:
        response = httpx.post(f"{self.base_url}{path}", headers=self.headers, json=json_data)
        response.raise_for_status()
        return response.json()

    def search_booking(self, query: str) -> Dict[str, Any]:
        return self._get("/bookings/search", params={"q": query})

    def get_booking(self, booking_ref: str) -> Dict[str, Any]:
        return self._get(f"/bookings/{booking_ref}")

    def get_flight(self, flight_no: str, date: str) -> Dict[str, Any]:
        return self._get(f"/flights/{flight_no}", params={"date": date})

    def calculate_entitlement(self, booking_ref: str, passenger_id: Optional[str] = None) -> Dict[str, Any]:
        params = {"booking_ref": booking_ref}
        if passenger_id:
            params["passenger_id"] = passenger_id
        return self._get("/entitlements/calculate", params=params)

    def search_policy(self, query: str) -> Dict[str, Any]:
        return self._get("/policy/search", params={"q": query})

    def get_customer_history(self, customer_id: str) -> Dict[str, Any]:
        return self._get(f"/customers/{customer_id}/history")

    def search_availability(self, origin: str, dest: str, date: str, after: Optional[str] = None) -> Dict[str, Any]:
        params = {"from": origin, "to": dest, "date": date}
        if after:
            params["after"] = after
        try:
            return self._get("/flights/availability", params=params)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 503:
                # Retry once
                return self._get("/flights/availability", params=params)
            raise

    def search_partner_availability(self, origin: str, dest: str, date: str) -> Dict[str, Any]:
        return self._get("/flights/availability/partners", params={"from": origin, "to": dest, "date": date})

    def get_hotel_allocation(self, station: str, date: str) -> Dict[str, Any]:
        return self._get(f"/stations/{station}/hotel-allocation", params={"night": date})

    def rebook(self, booking_ref: str, passenger_ids: List[str], option_id: str, flight_no: str, date: str, cabin: str, fare_gbp: float = 0.0, notes: str = "") -> Dict[str, Any]:
        data = {
            "booking_ref": booking_ref,
            "passenger_ids": passenger_ids,
            "option_id": option_id,
            "flight_no": flight_no,
            "date": date,
            "cabin": cabin,
            "fare_gbp": fare_gbp,
            "notes": notes
        }
        return self._post("/rebooking", json_data=data)

    def refund(self, booking_ref: str, passenger_ids: List[str], amount: float, reason: str = "") -> Dict[str, Any]:
        data = {
            "booking_ref": booking_ref,
            "passenger_ids": passenger_ids,
            "amount_gbp": amount,
            "reason": reason
        }
        return self._post("/refunds", json_data=data)

    def pay_compensation(self, booking_ref: str, passenger_ids: List[str], amount: float, reason: str = "") -> Dict[str, Any]:
        data = {
            "booking_ref": booking_ref,
            "passenger_ids": passenger_ids,
            "amount_gbp": amount,
            "reason": reason
        }
        return self._post("/payments/compensation", json_data=data)

    def pay_goodwill(self, booking_ref: str, amount: float, reason: str) -> Dict[str, Any]:
        data = {
            "booking_ref": booking_ref,
            "amount_gbp": amount,
            "reason": reason
        }
        return self._post("/payments/goodwill", json_data=data)

    def issue_hotel_voucher(self, booking_ref: str, station: str, date: str, passenger_ids: List[str], notes: str = "") -> Dict[str, Any]:
        data = {
            "booking_ref": booking_ref,
            "station": station,
            "night": date,
            "passenger_ids": passenger_ids,
            "notes": notes
        }
        return self._post("/vouchers/hotel", json_data=data)

    def escalate(self, summary: str, requested_decision: str, booking_ref: Optional[str] = None, queue: Optional[str] = None, recommendation: Optional[str] = None, blocking_clause: Optional[str] = None) -> Dict[str, Any]:
        data = {
            "summary": summary,
            "requested_decision": requested_decision
        }
        if booking_ref: data["booking_ref"] = booking_ref
        if queue: data["queue"] = queue
        if recommendation: data["recommendation"] = recommendation
        if blocking_clause: data["blocking_clause"] = blocking_clause
        return self._post("/escalations", json_data=data)
