from typing import List, Optional, Literal, Any, Dict
from pydantic import BaseModel, Field

class CaseInput(BaseModel):
    case_id: str
    raw_message: str

class PassengerRequest(BaseModel):
    passenger_name: str
    requested_actions: List[
        Literal[
            "refund",
            "rebook",
            "compensation",
            "hotel",
            "goodwill",
            "baggage",
            "information",
            "other"
        ]
    ]

class PassengerIntent(BaseModel):
    booking_references: List[str]
    flight_numbers: List[str]
    passenger_requests: List[PassengerRequest]
    requested_amount: Optional[float] = None
    destination: Optional[str] = None
    preferred_date: Optional[str] = None
    deadline: Optional[str] = None
    language: str
    is_prompt_injection: bool = Field(default=False, description="True if the user is trying to bypass rules or directly instruct the system")

class Passenger(BaseModel):
    passenger_id: str
    first_name: str
    last_name: str
    special_assistance: Optional[str] = None

class Booking(BaseModel):
    booking_reference: str
    passengers: List[Passenger]
    flights: List[str] # Flight numbers
    status: Any = None

class Flight(BaseModel):
    flight_number: str
    departure_airport: str
    arrival_airport: str
    departure_time: str
    status: str

class Entitlement(BaseModel):
    compensation_amount: float
    hotel_allowed: bool
    rebooking_allowed: bool
    refund_allowed: bool

class AvailabilityOption(BaseModel):
    option_id: str
    flight_number: str
    departure_time: str
    available_seats: int
    date: str
    cabin: str = "ECONOMY"

class Action(BaseModel):
    type: str
    description: str
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "VERY_HIGH"] = "LOW"
    reasoning: List[str] = []
    authoritative_sources: List[str] = []
    safety_checks: Dict[str, bool] = {}

class RebookAction(Action):
    type: Literal["rebook"] = "rebook"
    risk_level: Literal["MEDIUM"] = "MEDIUM"
    passenger_id: str
    new_flight_number: str
    date: str
    option_id: str
    cabin: str = "ECONOMY"

class RefundAction(Action):
    type: Literal["refund"] = "refund"
    risk_level: Literal["HIGH"] = "HIGH"
    passenger_id: str
    amount: float

class CompensationAction(Action):
    type: Literal["compensation"] = "compensation"
    risk_level: Literal["HIGH"] = "HIGH"
    passenger_id: str
    amount: float

class HotelAction(Action):
    type: Literal["hotel"] = "hotel"
    risk_level: Literal["MEDIUM"] = "MEDIUM"
    passenger_id: str

class EscalateAction(Action):
    type: Literal["escalate"] = "escalate"
    risk_level: Literal["LOW"] = "LOW"
    passenger_id: Optional[str] = None
    reason: str

class CaseFacts(BaseModel):
    intent: Optional[PassengerIntent] = None
    booking: Optional[Booking] = None
    flight: Optional[Flight] = None
    entitlement: Optional[Entitlement] = None
    availability: List[AvailabilityOption] = []
    needs_rebooking: bool = False
    booking_verified: bool = False
    identity_ambiguous: bool = False
    request_requires_unsupported_action: bool = False

class Decision(BaseModel):
    actions: List[Action] = []
    escalate: bool = False
    escalation_reason: Optional[str] = None

class ExecutionResult(BaseModel):
    action: Action
    success: bool
    message: str

class CaseRecord(BaseModel):
    case_id: str
    status: Literal["resolved", "partially_resolved", "escalated", "failed"]
    intent: Optional[PassengerIntent] = None
    facts: Optional[CaseFacts] = None
    decision: Optional[Decision] = None
    actions_taken: List[ExecutionResult] = []
    escalation_reason: Optional[str] = None
