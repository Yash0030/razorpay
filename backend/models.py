from pydantic import BaseModel
from typing import Optional

class Customer(BaseModel):
    id: str
    name: str
    risk_score: float
    total_spent: float
    preferred_payment_method: str

class Event(BaseModel):
    id: str
    type: str # "payment_failed", "checkout_abandoned", "invoice_overdue"
    amount: float
    currency: str = "INR"
    customer: Customer
    timestamp: str
    raw_reason: str
    status: str = "pending" # pending, recovering, recovered, lost
    
class AgentDecision(BaseModel):
    intervention: str
    reasoning: str
    confidence: float
    action_taken: str
    
class ProcessedEvent(BaseModel):
    event: Event
    decision: Optional[AgentDecision] = None
    final_status: str
    recovered_amount: float
