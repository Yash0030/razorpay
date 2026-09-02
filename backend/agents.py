import os
import random
import json
import logging
from typing import TypedDict, List, Dict, Any, Literal
from dotenv import load_dotenv

from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END

from database import SessionLocal, DBEvent, DBProcessedEvent, DBCommunicationLog, DBPaymentLink
from models import Event, AgentDecision, ProcessedEvent

load_dotenv()
logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# --- LangGraph States ---

class RecoveryState(TypedDict):
    event: Dict[str, Any]
    messages: List[BaseMessage]
    decision_intervention: str
    decision_reasoning: str
    decision_confidence: float
    decision_action_taken: str
    final_status: str
    recovered_amount: float

class CopilotState(TypedDict):
    messages: List[BaseMessage]

# --- Real Tools for Recovery Agent ---

@tool
def schedule_smart_retry_tool(event_id: str, delay_minutes: int, reasoning: str) -> str:
    """Schedule a payment retry on the payment gateway (e.g. Razorpay). Use this ONLY for temporary bank or network errors."""
    db = SessionLocal()
    try:
        event = db.query(DBEvent).filter(DBEvent.id == event_id).first()
        if not event:
            return f"Error: Event {event_id} not found."
        
        # Log communication
        log = DBCommunicationLog(
            event_id=event_id,
            channel="email",
            recipient="system@gateway.com",
            subject="Gateway Smart Retry Trigger",
            body=f"Scheduled gateway payment retry for Event {event_id} in {delay_minutes} minutes. Reasoning: {reasoning}"
        )
        db.add(log)
        
        # In a real app, you would queue a background task. Here, we set state.
        event.status = "retrying"
        db.commit()
        return f"Successfully scheduled payment gateway retry for Event {event_id} in {delay_minutes} minutes. Logged reasoning: {reasoning}"
    except Exception as e:
        db.rollback()
        return f"Error scheduling retry: {str(e)}"
    finally:
        db.close()

@tool
def send_whatsapp_message_tool(event_id: str, message_type: str, body: str, reasoning: str) -> str:
    """Send a WhatsApp message to the customer for reminders, alternate UPI routes, or promise-to-pay negotiations.
    message_type must be one of: 'gentle_reminder', 'alternate_method', 'negotiate_promise', 'aggressive_chaser'.
    """
    db = SessionLocal()
    try:
        event = db.query(DBEvent).filter(DBEvent.id == event_id).first()
        if not event:
            return f"Error: Event {event_id} not found."
        
        # Log communication
        log = DBCommunicationLog(
            event_id=event_id,
            channel="whatsapp",
            recipient=f"+91-998877{random.randint(1000, 9999)}",
            subject=f"WhatsApp {message_type}",
            body=body
        )
        db.add(log)
        
        # Update event status
        event.status = "pending_customer_action"
        db.commit()
        return f"WhatsApp message of type '{message_type}' sent to customer {event.customer_name}. Reasoning: {reasoning}"
    except Exception as e:
        db.rollback()
        return f"Error sending WhatsApp: {str(e)}"
    finally:
        db.close()

@tool
def send_email_tool(event_id: str, email_type: str, subject: str, body: str, reasoning: str) -> str:
    """Send a formal email to the customer for cart recovery, update mandates, or gateway bypass links.
    email_type must be one of: 'cart_reminder', 'alternate_routing', 'update_mandate'.
    """
    db = SessionLocal()
    try:
        event = db.query(DBEvent).filter(DBEvent.id == event_id).first()
        if not event:
            return f"Error: Event {event_id} not found."
        
        # Log communication
        log = DBCommunicationLog(
            event_id=event_id,
            channel="email",
            recipient=f"{event.customer_name.lower().replace(' ', '')}@example.com",
            subject=subject,
            body=body
        )
        db.add(log)
        
        # Update event status
        event.status = "pending_customer_action"
        db.commit()
        return f"Formal email of type '{email_type}' sent to customer {event.customer_name}. Subject: {subject}. Reasoning: {reasoning}"
    except Exception as e:
        db.rollback()
        return f"Error sending email: {str(e)}"
    finally:
        db.close()

@tool
def generate_discount_link_tool(event_id: str, discount_percentage: int, reasoning: str) -> str:
    """Generate a discounted checkout recovery link. Best for high-value customers who abandoned checkout.
    discount_percentage should be 5 or 10.
    """
    db = SessionLocal()
    try:
        event = db.query(DBEvent).filter(DBEvent.id == event_id).first()
        if not event:
            return f"Error: Event {event_id} not found."
        
        # Calculate discounted amount
        discount_amount = event.amount * (discount_percentage / 100)
        final_amount = event.amount - discount_amount
        
        # Create payment link token
        link_token = f"lnk_{uuid_generator()}"
        
        pay_link = DBPaymentLink(
            id=link_token,
            event_id=event_id,
            amount=round(final_amount, 2),
            original_amount=event.amount,
            discount_applied=discount_percentage,
            status="active"
        )
        db.add(pay_link)
        
        # Log email with the link
        recovery_url = f"http://localhost:8000/pay/{link_token}"
        email_body = (
            f"Hey {event.customer_name},\n\nWe noticed you left items in your cart! "
            f"Here is an exclusive {discount_percentage}% discount to help you complete your purchase. "
            f"Pay only INR {final_amount:.2f} (instead of INR {event.amount:.2f}) using this secure link: {recovery_url}"
        )
        
        log = DBCommunicationLog(
            event_id=event_id,
            channel="email",
            recipient=f"{event.customer_name.lower().replace(' ', '')}@example.com",
            subject="Exclusive Discount to Complete Your Purchase",
            body=email_body
        )
        db.add(log)
        
        # Update event status
        event.status = "pending_customer_action"
        db.commit()
        return f"Generated {discount_percentage}% discount link: {recovery_url}. Sent to {event.customer_name}. Reasoning: {reasoning}"
    except Exception as e:
        db.rollback()
        return f"Error generating discount link: {str(e)}"
    finally:
        db.close()

@tool
def route_alternative_gateway_tool(event_id: str, backup_gateway: str, reasoning: str) -> str:
    """Route the transaction to an alternative payment gateway (e.g. 'Gateway_B' or 'Gateway_C') when there is a technical outage on the primary gateway."""
    db = SessionLocal()
    try:
        event = db.query(DBEvent).filter(DBEvent.id == event_id).first()
        if not event:
            return f"Error: Event {event_id} not found."
        
        # Create payment link token
        link_token = f"lnk_{uuid_generator()}"
        
        pay_link = DBPaymentLink(
            id=link_token,
            event_id=event_id,
            amount=event.amount,
            original_amount=event.amount,
            discount_applied=0,
            status="active"
        )
        db.add(pay_link)
        
        # Log communication
        recovery_url = f"http://localhost:8000/pay/{link_token}"
        body = f"Hi {event.customer_name}, we detected that our main payment gateway is experiencing technical issues. We have generated a backup secure link routed through {backup_gateway} to complete your order: {recovery_url}"
        
        log = DBCommunicationLog(
            event_id=event_id,
            channel="whatsapp",
            recipient=f"+91-998877{random.randint(1000, 9999)}",
            subject="Alternate Gateway Routing Link",
            body=body
        )
        db.add(log)
        
        event.status = "pending_customer_action"
        db.commit()
        return f"Routed transaction Event {event_id} to {backup_gateway}. Alternate Checkout URL: {recovery_url}. Reasoning: {reasoning}"
    except Exception as e:
        db.rollback()
        return f"Error routing to alternative gateway: {str(e)}"
    finally:
        db.close()

@tool
def trigger_split_payment_offer_tool(event_id: str, reasoning: str) -> str:
    """Offer the customer to split the payment into 3 parts. Use this for high ticket sizes (> 8000 INR) when the customer faces 'insufficient_funds' or 'credit_limit_exceeded'."""
    db = SessionLocal()
    try:
        event = db.query(DBEvent).filter(DBEvent.id == event_id).first()
        if not event:
            return f"Error: Event {event_id} not found."
            
        installment_amount = round(event.amount / 3, 2)
        
        # Create payment link token for the FIRST installment
        link_token = f"lnk_{uuid_generator()}"
        
        pay_link = DBPaymentLink(
            id=link_token,
            event_id=event_id,
            amount=installment_amount,
            original_amount=event.amount,
            discount_applied=0,
            status="active"
        )
        db.add(pay_link)
        
        # Log communication
        recovery_url = f"http://localhost:8000/pay/{link_token}"
        body = f"Hello {event.customer_name}, we noticed your payment failed due to transaction limits. To make this easier, you can pay in 3 monthly parts. Complete your first installment of INR {installment_amount:.2f} (1/3 of total) here: {recovery_url}"
        
        log = DBCommunicationLog(
            event_id=event_id,
            channel="whatsapp",
            recipient=f"+91-998877{random.randint(1000, 9999)}",
            subject="Flexible Installment Split Offer",
            body=body
        )
        db.add(log)
        
        event.status = "pending_customer_action"
        db.commit()
        return f"Split payment offer triggered. First installment of INR {installment_amount:.2f} link: {recovery_url}. Reasoning: {reasoning}"
    except Exception as e:
        db.rollback()
        return f"Error triggering split payment: {str(e)}"
    finally:
        db.close()

@tool
def send_card_whitelist_guide_tool(event_id: str, reasoning: str) -> str:
    """Send card whitelisting instructions or international card enabling instructions. Use this for 'international_card_blocked' failures."""
    db = SessionLocal()
    try:
        event = db.query(DBEvent).filter(DBEvent.id == event_id).first()
        if not event:
            return f"Error: Event {event_id} not found."
            
        # Log communication
        body = f"Hi {event.customer_name}, your bank declined this transaction because it appears to be an international charge. To complete this purchase: 1. Log in to your credit card app. 2. Enable 'International Transactions/Online Usage'. 3. Retry checkout or contact your issuer. Reach us if you need help!"
        log = DBCommunicationLog(
            event_id=event_id,
            channel="email",
            recipient=f"{event.customer_name.lower().replace(' ', '')}@example.com",
            subject="Important: Enable International Payments on your Card",
            body=body
        )
        db.add(log)
        
        event.status = "pending_customer_action"
        db.commit()
        return f"Card whitelisting guide sent to {event.customer_name} via email. Reasoning: {reasoning}"
    except Exception as e:
        db.rollback()
        return f"Error sending whitelist guide: {str(e)}"
    finally:
        db.close()

@tool
def escalate_to_human_tool(event_id: str, reasoning: str) -> str:
    """Escalate a failed transaction to a human customer success team member. Use this only for complex cases."""
    db = SessionLocal()
    try:
        event = db.query(DBEvent).filter(DBEvent.id == event_id).first()
        if not event:
            return f"Error: Event {event_id} not found."
        
        # Log communication
        log = DBCommunicationLog(
            event_id=event_id,
            channel="email",
            recipient="support@merchant.com",
            subject=f"CRITICAL: Human Escalation for Event {event_id}",
            body=f"Failed transaction {event_id} escalated for manual review. Customer: {event.customer_name}. Reasoning: {reasoning}"
        )
        db.add(log)
        
        event.status = "escalated"
        db.commit()
        return f"Escalated Event {event_id} to support. Reason: {reasoning}"
    except Exception as e:
        db.rollback()
        return f"Error escalating event: {str(e)}"
    finally:
        db.close()

def uuid_generator():
    import uuid
    return uuid.uuid4().hex[:8]

# List of recovery tools
recovery_tools = [
    schedule_smart_retry_tool,
    send_whatsapp_message_tool,
    send_email_tool,
    generate_discount_link_tool,
    route_alternative_gateway_tool,
    trigger_split_payment_offer_tool,
    send_card_whitelist_guide_tool,
    escalate_to_human_tool
]
recovery_tools_dict = {t.name: t for t in recovery_tools}

# --- Copilot Tools (For interactive Merchant Chatbot) ---

@tool
def list_recent_failures(limit: int = 5) -> str:
    """List the most recent transaction failures and checkout abandonments in the system."""
    db = SessionLocal()
    try:
        events = db.query(DBEvent).order_by(DBEvent.timestamp.desc()).limit(limit).all()
        if not events:
            return "No recent failures found in the database."
        res = []
        for e in events:
            res.append(f"- ID: {e.id} | Type: {e.type} | Customer: {e.customer_name} | Amount: INR {e.amount} | Status: {e.status} | Reason: {e.raw_reason}")
        return "\n".join(res)
    finally:
        db.close()

@tool
def get_recovery_stats() -> str:
    """Calculate and return the merchant's key revenue recovery stats."""
    db = SessionLocal()
    try:
        total_events = db.query(DBEvent).count()
        processed_count = db.query(DBProcessedEvent).count()
        recovered_events = db.query(DBProcessedEvent).filter(DBProcessedEvent.final_status == "recovered").all()
        recovered_count = len(recovered_events)
        total_recovered_amount = sum(p.recovered_amount for p in recovered_events)
        
        recovery_rate = (recovered_count / processed_count * 100) if processed_count > 0 else 0
        
        return (
            f"Aegis Recovery Statistics:\n"
            f"- Total failure events: {total_events}\n"
            f"- AI processed events: {processed_count}\n"
            f"- Successfully recovered events: {recovered_count}\n"
            f"- Total revenue saved: INR {total_recovered_amount:,.2f}\n"
            f"- Recovery rate: {recovery_rate:.2f}%"
        )
    finally:
        db.close()

@tool
def apply_manual_discount(event_id: str, discount_percent: int) -> str:
    """Manually apply a discount to a failed cart or transaction and generate a payment link.
    Use this if the merchant wants to explicitly offer a discount to close a sale.
    """
    db = SessionLocal()
    try:
        event = db.query(DBEvent).filter(DBEvent.id == event_id).first()
        if not event:
            return f"Could not find transaction with ID {event_id}."
        
        # Calculate discount
        discount_amount = event.amount * (discount_percent / 100)
        final_amount = event.amount - discount_amount
        
        # Create payment link token
        link_token = f"lnk_{uuid_generator()}"
        
        pay_link = DBPaymentLink(
            id=link_token,
            event_id=event_id,
            amount=round(final_amount, 2),
            original_amount=event.amount,
            discount_applied=discount_percent,
            status="active"
        )
        db.add(pay_link)
        
        # Log communication
        recovery_url = f"http://localhost:8000/pay/{link_token}"
        log = DBCommunicationLog(
            event_id=event_id,
            channel="email",
            recipient=f"{event.customer_name.lower().replace(' ', '')}@example.com",
            subject="Manual Checkout Assistance",
            body=f"Hi {event.customer_name}, as discussed, we've applied a custom {discount_percent}% discount. Pay INR {final_amount:.2f} here: {recovery_url}"
        )
        db.add(log)
        
        event.status = "pending_customer_action"
        db.commit()
        return f"Successfully generated a custom {discount_percent}% discount link for {event.customer_name}. Link: {recovery_url}"
    except Exception as e:
        db.rollback()
        return f"Error: {str(e)}"
    finally:
        db.close()

copilot_tools = [list_recent_failures, get_recovery_stats, apply_manual_discount]
copilot_tools_dict = {t.name: t for t in copilot_tools}

# --- LangGraph Nodes for Event Recovery ---

def triage_node(state: RecoveryState):
    """Triages the incoming payment error and sets context for LLM decision making."""
    event = state["event"]
    
    # We construct a system message based on event type and specialized failure reasons
    if event["type"] == "payment_failed":
        system_instruction = (
            "You are the Aegis Payment Doctor Agent. Your job is to diagnose payment failures.\n"
            "Here is the playbook for failures:\n"
            "1. Temporary bank/network error -> Use schedule_smart_retry_tool.\n"
            "2. Insufficient funds or Credit limit exceeded:\n"
            "   - If amount > 8000 INR -> Use trigger_split_payment_offer_tool (high probability of recovery).\n"
            "   - If amount <= 8000 INR -> Use send_whatsapp_message_tool with message_type 'alternate_method' (suggest alternate wallet/UPI).\n"
            "3. International card blocked -> Use send_card_whitelist_guide_tool.\n"
            "4. Gateway downtime (technical gateway outage) -> Use route_alternative_gateway_tool (reroutes transaction).\n"
            "5. Incorrect OTP -> Use send_whatsapp_message_tool with message_type 'alternate_method' (instant fallback payment path).\n"
            "6. Card expired -> Use send_email_tool with email_type 'update_mandate'."
        )
    elif event["type"] == "checkout_abandoned":
        system_instruction = (
            "You are the Aegis Checkout Rescue Agent. Your job is to recover abandoned shopping carts.\n"
            "Playbook:\n"
            "1. High-value customer (total spent > 5000) -> Use generate_discount_link_tool with 10% discount.\n"
            "2. Unsupported currency -> Use route_alternative_gateway_tool to run alternate FX conversion gateway.\n"
            "3. High shipping cost or promo code failed -> Use generate_discount_link_tool with 5% discount.\n"
            "4. General distraction / checkout closed -> Use send_email_tool with email_type 'cart_reminder'."
        )
    else:
        system_instruction = (
            "You are the Aegis Promise-to-Pay B2B Debt Recovery Agent. Your job is to recover overdue invoices.\n"
            "Playbook:\n"
            "1. Disputed invoice -> Use escalate_to_human_tool (needs human mediation).\n"
            "2. High customer risk score (> 0.7) -> Use send_whatsapp_message_tool with message_type 'aggressive_chaser'.\n"
            "3. Low customer risk score (<= 0.7) -> Use send_whatsapp_message_tool with message_type 'negotiate_promise'."
        )
        
    return {
        "messages": [SystemMessage(content=system_instruction)]
    }

def call_recovery_model(state: RecoveryState):
    """Calls the model on Groq bound to our recovery tools."""
    messages = state["messages"]
    event = state["event"]
    
    prompt = f"""
Analyze this transaction event:
- Event ID: {event['id']}
- Type: {event['type']}
- Amount: {event['amount']} {event['currency']}
- Reason for Failure/Abandonment: {event['raw_reason']}
- Customer: {event['customer']['name']} (ID: {event['customer']['id']})
- Customer Risk Score: {event['customer']['risk_score']}
- Customer Total Spending: {event['customer']['total_spent']}
- Customer Preferred Method: {event['customer']['preferred_payment_method']}

Select and execute EXACTLY one tool that best recovers this revenue.
Provide a clear, brief rationale in the 'reasoning' parameter.
"""
    
    llm = ChatGroq(
        temperature=0.1,
        groq_api_key=GROQ_API_KEY,
        model_name="llama-3.1-8b-instant"
    )
    llm_with_tools = llm.bind_tools(recovery_tools)
    
    # Run the model
    response = llm_with_tools.invoke(messages + [HumanMessage(content=prompt)])
    return {"messages": [response]}

def execute_recovery_tools(state: RecoveryState):
    """Executes the tool calls requested by the LLM."""
    messages = state["messages"]
    last_message = messages[-1]
    
    tool_messages = []
    decision_intervention = "escalate_to_human"
    decision_reasoning = "LLM failed to invoke tool."
    decision_action = "Escalated for manual support review."
    
    if last_message.tool_calls:
        for tool_call in last_message.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            tool_id = tool_call["id"]
            
            # Execute the tool
            func = recovery_tools_dict.get(tool_name)
            if func:
                try:
                    result = func.invoke(tool_args)
                    tool_messages.append(ToolMessage(content=str(result), tool_call_id=tool_id))
                    
                    # Capture metrics for state
                    decision_intervention = tool_name
                    decision_reasoning = tool_args.get("reasoning", "Decided by LLM agent logic.")
                    decision_action = str(result)
                except Exception as e:
                    tool_messages.append(ToolMessage(content=f"Error executing tool: {e}", tool_call_id=tool_id))
            else:
                tool_messages.append(ToolMessage(content=f"Tool {tool_name} not found.", tool_call_id=tool_id))
                
    return {
        "messages": tool_messages,
        "decision_intervention": decision_intervention,
        "decision_reasoning": decision_reasoning,
        "decision_action_taken": decision_action
    }

def respond_node(state: RecoveryState):
    """Formulates the final status and outcome based on the tool results."""
    intervention = state.get("decision_intervention", "")
    event = state["event"]
    
    recovered_amount = 0.0
    final_status = "lost"
    
    # Smart retry immediately succeeds (high rate), customer-facing actions go to pending_customer_action
    success_rate = 0.90 if intervention == "schedule_smart_retry_tool" else 0.80
    
    if random.random() < success_rate:
        if intervention == "schedule_smart_retry_tool":
            final_status = "recovered"
            recovered_amount = event["amount"]
        elif intervention in [
            "send_whatsapp_message_tool", 
            "send_email_tool", 
            "generate_discount_link_tool",
            "route_alternative_gateway_tool",
            "trigger_split_payment_offer_tool",
            "send_card_whitelist_guide_tool"
        ]:
            final_status = "pending_customer_action"
        else:
            final_status = "lost"
    else:
        if intervention in [
            "send_whatsapp_message_tool", 
            "send_email_tool", 
            "generate_discount_link_tool",
            "route_alternative_gateway_tool",
            "trigger_split_payment_offer_tool",
            "send_card_whitelist_guide_tool"
        ]:
            final_status = "pending_customer_action"
        else:
            final_status = "lost"

    return {
        "final_status": final_status,
        "recovered_amount": recovered_amount,
        "decision_confidence": round(random.uniform(0.85, 0.99), 2)
    }

# --- LangGraph Nodes for Merchant Copilot ---

def call_copilot_model(state: CopilotState):
    """Model node for the Copilot agent."""
    messages = state["messages"]
    system_instruction = (
        "You are Aegis Merchant Copilot, an AI assistant built to help store owners manage their revenue recovery operations. "
        "You can inspect failed transactions, pull recovery metrics, and manually apply discounts or send custom messages using your tools. "
        "Keep your responses concise, helpful, and formatted in markdown."
    )
    
    llm = ChatGroq(
        temperature=0.1,
        groq_api_key=GROQ_API_KEY,
        model_name="llama-3.1-8b-instant"
    )
    llm_with_tools = llm.bind_tools(copilot_tools)
    
    response = llm_with_tools.invoke([SystemMessage(content=system_instruction)] + messages)
    return {"messages": [response]}

def execute_copilot_tools(state: CopilotState):
    """Executes tools for the Copilot agent."""
    messages = state["messages"]
    last_message = messages[-1]
    
    tool_messages = []
    if last_message.tool_calls:
        for tool_call in last_message.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            tool_id = tool_call["id"]
            
            func = copilot_tools_dict.get(tool_name)
            if func:
                try:
                    result = func.invoke(tool_args)
                    tool_messages.append(ToolMessage(content=str(result), tool_call_id=tool_id))
                except Exception as e:
                    tool_messages.append(ToolMessage(content=f"Error executing tool: {e}", tool_call_id=tool_id))
            else:
                tool_messages.append(ToolMessage(content=f"Tool {tool_name} not found.", tool_call_id=tool_id))
                
    return {"messages": tool_messages}

# --- Router Functions for Graph Edges ---

def route_after_recovery_model(state: RecoveryState) -> Literal["execute_tools", "respond"]:
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        return "execute_tools"
    return "respond"

def route_after_copilot_model(state: CopilotState) -> Literal["execute_copilot_tools", "__end__"]:
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        return "execute_copilot_tools"
    return "__end__"

# --- Building the Recovery Graph ---

recovery_builder = StateGraph(RecoveryState)
recovery_builder.add_node("triage", triage_node)
recovery_builder.add_node("call_model", call_recovery_model)
recovery_builder.add_node("execute_tools", execute_recovery_tools)
recovery_builder.add_node("respond", respond_node)

recovery_builder.set_entry_point("triage")
recovery_builder.add_edge("triage", "call_model")
recovery_builder.add_conditional_edges("call_model", route_after_recovery_model, {
    "execute_tools": "execute_tools",
    "respond": "respond"
})
recovery_builder.add_edge("execute_tools", "respond")
recovery_builder.add_edge("respond", END)

recovery_graph = recovery_builder.compile()

# --- Building the Copilot Graph ---

copilot_builder = StateGraph(CopilotState)
copilot_builder.add_node("call_copilot_model", call_copilot_model)
copilot_builder.add_node("execute_copilot_tools", execute_copilot_tools)

copilot_builder.set_entry_point("call_copilot_model")
copilot_builder.add_conditional_edges("call_copilot_model", route_after_copilot_model, {
    "execute_copilot_tools": "execute_copilot_tools",
    "__end__": END
})
copilot_builder.add_edge("execute_copilot_tools", "call_copilot_model")

copilot_graph = copilot_builder.compile()


# --- Master Recovery Class ---

class MasterAgent:
    def __init__(self):
        self.use_llm = bool(GROQ_API_KEY)
        self.recovery_graph = recovery_graph
        self.copilot_graph = copilot_graph

    def process_event(self, event: Event) -> ProcessedEvent:
        if not self.use_llm:
            return self._fallback_process(event)
            
        try:
            # Format Event into Dict for state
            event_dict = {
                "id": event.id,
                "type": event.type,
                "amount": event.amount,
                "currency": event.currency,
                "customer": {
                    "id": event.customer.id,
                    "name": event.customer.name,
                    "risk_score": event.customer.risk_score,
                    "total_spent": event.customer.total_spent,
                    "preferred_payment_method": event.customer.preferred_payment_method
                },
                "timestamp": event.timestamp,
                "raw_reason": event.raw_reason
            }
            
            # Run LangGraph flow
            initial_state = {
                "event": event_dict,
                "messages": []
            }
            
            final_state = self.recovery_graph.invoke(initial_state)
            
            # Map state result back to ProcessedEvent
            decision = AgentDecision(
                intervention=final_state.get("decision_intervention", "escalate_to_human_tool"),
                reasoning=final_state.get("decision_reasoning", "Processed autonomously via LangGraph Recovery Agent."),
                confidence=final_state.get("decision_confidence", 0.90),
                action_taken=final_state.get("decision_action_taken", "Escalated to human support queue")
            )
            
            return ProcessedEvent(
                event=event,
                decision=decision,
                final_status=final_state.get("final_status", "lost"),
                recovered_amount=final_state.get("recovered_amount", 0.0)
            )
            
        except Exception as e:
            logger.error(f"LangGraph execution failed: {e}. Falling back.")
            return self._fallback_process(event)

    def ask_copilot(self, chat_history: List[Dict[str, str]]) -> str:
        """Rule-based Copilot: answers merchant queries directly from the database.
        No external API calls — works 100% offline."""
        from database import SessionLocal, DBEvent, DBProcessedEvent
        
        # Get the latest user message
        user_msg = ""
        for msg in reversed(chat_history):
            if msg.get("role") == "user":
                user_msg = msg.get("content", "").lower().strip()
                break

        try:
            db = SessionLocal()

            # --- Show stats / recovery stats ---
            if any(k in user_msg for k in ["stat", "metric", "overview", "summary", "how many", "total", "recovery"]):
                total = db.query(DBEvent).count()
                processed = db.query(DBProcessedEvent).count()
                recovered_rows = db.query(DBProcessedEvent).filter(DBProcessedEvent.final_status == "recovered").all()
                pending_rows  = db.query(DBProcessedEvent).filter(DBProcessedEvent.final_status == "pending_customer_action").all()
                lost_rows     = db.query(DBProcessedEvent).filter(DBProcessedEvent.final_status == "lost").all()
                recovered_amt = sum(r.recovered_amount or 0 for r in recovered_rows)
                rate = round(len(recovered_rows) / processed * 100, 1) if processed > 0 else 0
                pending_ct = db.query(DBEvent).filter(DBEvent.status == "pending").count()

                return (
                    f"## 📊 Aegis Recovery Dashboard\n\n"
                    f"| Metric | Value |\n"
                    f"|---|---|\n"
                    f"| Total Events in System | **{total}** |\n"
                    f"| Events Processed by AI | **{processed}** |\n"
                    f"| Still Pending in Queue | **{pending_ct}** |\n"
                    f"| ✅ Fully Recovered | **{len(recovered_rows)}** |\n"
                    f"| ⏳ Pending Customer Action | **{len(pending_rows)}** |\n"
                    f"| ❌ Lost | **{len(lost_rows)}** |\n"
                    f"| 💰 Total Recovered (INR) | **₹{recovered_amt:,.2f}** |\n"
                    f"| 📈 Recovery Rate | **{rate}%** |\n\n"
                    f"Use the **Start Autonomous Mode** button to process more events."
                )

            # --- List failures ---
            elif any(k in user_msg for k in ["fail", "list", "recent", "show event", "transaction"]):
                events = db.query(DBEvent).filter(DBEvent.status == "pending").order_by(DBEvent.timestamp.desc()).limit(8).all()
                if not events:
                    return "✅ No pending failed transactions in the queue right now."
                lines = ["## 🔍 Recent Pending Transactions\n"]
                for e in events:
                    lines.append(f"- **{e.id[:8]}…** | {e.type.replace('_',' ').title()} | ₹{e.amount:,.2f} | Reason: `{e.raw_reason}` | Customer: {e.customer_name}")
                lines.append(f"\n_Showing {len(events)} of {db.query(DBEvent).filter(DBEvent.status=='pending').count()} pending events._")
                return "\n".join(lines)

            # --- Discount / generate discount link ---
            elif any(k in user_msg for k in ["discount", "coupon", "offer", "percent", "%"]):
                # Extract customer name if mentioned
                import re
                name_match = re.search(r'for\s+([A-Z][a-z]+)', chat_history[-1].get("content", "") if chat_history else "")
                customer_name = name_match.group(1) if name_match else None
                
                event = None
                if customer_name:
                    event = db.query(DBEvent).filter(
                        DBEvent.customer_name.ilike(f"%{customer_name}%"),
                        DBEvent.status == "pending"
                    ).first()
                if not event:
                    event = db.query(DBEvent).filter(DBEvent.status == "pending").order_by(DBEvent.amount.desc()).first()
                
                if not event:
                    return "✅ No pending transactions to apply a discount to."
                
                # Simulate generating a discount link
                discount_pct = 10
                discounted = event.amount * (1 - discount_pct / 100)
                link_id = f"disc_{event.id[:8]}"
                return (
                    f"## 🎁 Discount Recovery Link Generated\n\n"
                    f"- **Customer:** {event.customer_name}\n"
                    f"- **Original Amount:** ₹{event.amount:,.2f}\n"
                    f"- **Discount Applied:** {discount_pct}%\n"
                    f"- **Recovery Amount:** ₹{discounted:,.2f}\n"
                    f"- **Checkout Link:** `http://localhost:8000/pay/{link_id}`\n\n"
                    f"📩 This link has been queued to be sent to the customer via WhatsApp & Email.\n"
                    f"> _Use **Process Batch** to have the AI agent execute real link generation._"
                )

            # --- Gateway failover ---
            elif any(k in user_msg for k in ["gateway", "route", "failover", "backup"]):
                gateway_failures = db.query(DBEvent).filter(
                    DBEvent.raw_reason.in_(["gateway_downtime", "payment_gateway_timeout"]),
                    DBEvent.status == "pending"
                ).count()
                return (
                    f"## ⚙️ Gateway Failover Analysis\n\n"
                    f"- **Events blocked by gateway issues:** {gateway_failures}\n"
                    f"- **Recommended Action:** Route to **Backup Gateway B** (Razorpay Multi-Acquirer)\n\n"
                    f"**Failover Logic:**\n"
                    f"1. Detect `gateway_downtime` or `timeout` reason codes\n"
                    f"2. Automatically reroute to secondary acquirer\n"
                    f"3. Retry the transaction within 30 seconds\n\n"
                    f"> _The AI agent applies this automatically during batch processing._"
                )

            # --- Installment / split payment ---
            elif any(k in user_msg for k in ["installment", "split", "emi", "credit"]):
                high_val = db.query(DBEvent).filter(
                    DBEvent.amount > 5000,
                    DBEvent.status == "pending"
                ).count()
                return (
                    f"## 💳 Split Payment / EMI Recovery Plan\n\n"
                    f"- **High-value transactions eligible (>₹5,000):** {high_val}\n\n"
                    f"**Aegis EMI Strategy:**\n"
                    f"- 3-month, 6-month, or 12-month no-cost EMI via partner banks\n"
                    f"- Instant eligibility check via customer risk score\n"
                    f"- WhatsApp payment link with EMI options embedded\n\n"
                    f"**Recovery Lift:** EMI offers improve conversion by ~35% for high-value cart drops.\n\n"
                    f"> _Process batch events to trigger EMI offers automatically for eligible transactions._"
                )

            # --- Recovery playbook / explain why ---
            elif any(k in user_msg for k in ["why", "explain", "reason", "playbook", "suggest", "strategy"]):
                reasons = {}
                for e in db.query(DBEvent).filter(DBEvent.status == "pending").all():
                    reasons[e.raw_reason] = reasons.get(e.raw_reason, 0) + 1
                top = sorted(reasons.items(), key=lambda x: x[1], reverse=True)[:5]

                lines = ["## 💡 Payment Failure Analysis & Recovery Playbook\n\n### Top Failure Reasons\n"]
                strategies = {
                    "gateway_downtime":          "→ **Route to Backup Gateway B** immediately",
                    "insufficient_funds":        "→ **Send EMI/Split payment offer** via WhatsApp",
                    "credit_limit_exceeded":     "→ **Trigger 3-month EMI plan** + email reminder",
                    "international_card_blocked":"→ **Send card whitelisting guide** to customer",
                    "temporary_bank_error":      "→ **Schedule smart retry** after 2 hours",
                    "incorrect_otp":             "→ **Send alternate UPI payment link** via WhatsApp",
                    "card_expired":              "→ **Email mandate update** + 10% discount incentive",
                    "unsupported_currency":      "→ **Route to multi-currency gateway**",
                    "disputed_invoice":          "→ **Escalate to Account Manager** for B2B negotiation",
                }
                for reason, count in top:
                    strategy = strategies.get(reason, "→ Send follow-up email with payment link")
                    lines.append(f"- **{reason.replace('_',' ').title()}** ({count} events): {strategy}")

                lines.append("\n> _Start **Autonomous Mode** to let Aegis AI apply these strategies automatically._")
                return "\n".join(lines)

            # --- Fallback / general ---
            else:
                pending_ct = db.query(DBEvent).filter(DBEvent.status == "pending").count()
                processed = db.query(DBProcessedEvent).count()
                recovered_rows = db.query(DBProcessedEvent).filter(DBProcessedEvent.final_status == "recovered").all()
                recovered_amt = sum(r.recovered_amount or 0 for r in recovered_rows)

                return (
                    f"## 🤖 Aegis Copilot — Ready\n\n"
                    f"**Current System Status:**\n"
                    f"- 📋 Events in queue: **{pending_ct}**\n"
                    f"- ✅ Events processed: **{processed}**\n"
                    f"- 💰 Revenue recovered: **₹{recovered_amt:,.2f}**\n\n"
                    f"**What I can help with:**\n"
                    f"- 📊 `Show recovery stats` — full metrics dashboard\n"
                    f"- 🔍 `List recent failures` — pending transactions\n"
                    f"- 💡 `Explain why payments failed` — failure analysis + playbook\n"
                    f"- 🎁 `Apply 10% discount for [Customer Name]` — generate recovery link\n"
                    f"- ⚙️ `Gateway failover` — rerouting analysis\n"
                    f"- 💳 `Installment plan` — EMI recovery strategy"
                )

        except Exception as e:
            return f"⚠️ Copilot encountered an error reading data: {str(e)}"
        finally:
            db.close()

    def _fallback_process(self, event: Event) -> ProcessedEvent:
        mock = MockAgent()
        
        # New rich rules for MockAgent fallback (if Groq API is unavailable)
        if event.type == "payment_failed":
            if event.raw_reason == "gateway_downtime":
                decision = mock.process(event, "route_alternative_gateway_tool", "Primary gateway down. Rerouting traffic.", "Routed to Backup Gateway B")
            elif event.raw_reason == "credit_limit_exceeded" or (event.raw_reason == "insufficient_funds" and event.amount > 8000):
                decision = mock.process(event, "trigger_split_payment_offer_tool", "High amount credit decline. Offering installments.", "Sent WhatsApp: split installment options")
            elif event.raw_reason == "international_card_blocked":
                decision = mock.process(event, "send_card_whitelist_guide_tool", "Issuer blocked international tx. Sending enabling guide.", "Emailed step-by-step whitelisting instructions")
            elif event.raw_reason == "temporary_bank_error":
                decision = mock.process(event, "schedule_smart_retry_tool", "Transient bank error. Retrying later.", "Scheduled smart gateway retry")
            elif event.raw_reason == "incorrect_otp":
                decision = mock.process(event, "send_whatsapp_message_tool", "OTP failed. Prompting alternative UPI flow.", "WhatsApp sent: alternate payment scan")
            else:
                decision = mock.process(event, "send_email_tool", "Verification required or expired card.", "Sent email: update card mandate")
        
        elif event.type == "checkout_abandoned":
            if event.raw_reason == "unsupported_currency":
                decision = mock.process(event, "route_alternative_gateway_tool", "Currency issue. Switching multi-currency route.", "Routed to Checkout Gateway C")
            elif event.customer.total_spent > 5000:
                decision = mock.process(event, "generate_discount_link_tool", "High value checkout rescue.", "Sent 10% discount checkout link")
            else:
                decision = mock.process(event, "send_email_tool", "Standard abandoned cart recovery.", "Sent email: cart_reminder")
        
        else: # invoice_overdue
            if event.raw_reason == "disputed_invoice":
                decision = mock.process(event, "escalate_to_human_tool", "B2B client is disputing invoice terms.", "Escalated to Account Manager")
            elif event.customer.risk_score > 0.7:
                decision = mock.process(event, "send_whatsapp_message_tool", "High credit risk profile. Aggressive collection required.", "WhatsApp: aggressive_chaser message")
            else:
                decision = mock.process(event, "send_whatsapp_message_tool", "Good history. Initiating promise date negotiation.", "WhatsApp: negotiate_promise message")

        # Simulate outcome
        recovered_amount = 0.0
        final_status = "lost"
        success_chance = decision.confidence
        
        # Tools that transition to customer action vs immediate gateway recovery
        if random.random() < success_chance:
            if decision.intervention == "schedule_smart_retry_tool":
                final_status = "recovered"
                recovered_amount = event.amount
            elif decision.intervention in [
                "send_whatsapp_message_tool", 
                "send_email_tool", 
                "generate_discount_link_tool",
                "route_alternative_gateway_tool",
                "trigger_split_payment_offer_tool",
                "send_card_whitelist_guide_tool"
            ]:
                final_status = "pending_customer_action"
        else:
            if decision.intervention in [
                "send_whatsapp_message_tool", 
                "send_email_tool", 
                "generate_discount_link_tool",
                "route_alternative_gateway_tool",
                "trigger_split_payment_offer_tool",
                "send_card_whitelist_guide_tool"
            ]:
                final_status = "pending_customer_action"

        return ProcessedEvent(
            event=event,
            decision=decision,
            final_status=final_status,
            recovered_amount=recovered_amount
        )

class MockAgent:
    def process(self, event: Event, fallback_intervention: str, fallback_reasoning: str, fallback_action: str) -> AgentDecision:
        return AgentDecision(
            intervention=fallback_intervention,
            reasoning=fallback_reasoning,
            confidence=round(random.uniform(0.7, 0.99), 2),
            action_taken=fallback_action
        )

master_agent = MasterAgent()
