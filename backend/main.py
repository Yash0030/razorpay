import time
from fastapi import FastAPI, Depends, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from pydantic import BaseModel

from models import Event, Customer, ProcessedEvent, AgentDecision
from database import get_db, seed_database, DBEvent, DBProcessedEvent, DBPaymentLink, DBCommunicationLog, Base, engine
from agents import master_agent

app = FastAPI(title="Aegis AI Revenue Recovery (Scalable LLM Agent Edition)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Seed initial data if DB is empty
with Session(engine) as db:
    try:
        if db.query(DBEvent).count() == 0:
            seed_database(db, 150)
    except Exception as e:
        print(f"Error seeding database on start: {e}. Check if PostgreSQL is running and DB exists.")

# --- Models for Copilot Chat ---
class ChatMessage(BaseModel):
    role: str # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    history: List[ChatMessage]

# --- Helper Functions ---
def _map_db_event_to_pydantic(db_event: DBEvent) -> Event:
    return Event(
        id=db_event.id,
        type=db_event.type,
        amount=db_event.amount,
        currency=db_event.currency,
        customer=Customer(
            id=db_event.customer_id,
            name=db_event.customer_name,
            risk_score=db_event.customer_risk_score,
            total_spent=db_event.customer_total_spent,
            preferred_payment_method=db_event.customer_preferred_payment_method
        ),
        timestamp=db_event.timestamp,
        raw_reason=db_event.raw_reason,
        status=db_event.status
    )

def _map_db_processed_to_pydantic(db_processed: DBProcessedEvent, db_event: DBEvent) -> ProcessedEvent:
    event = _map_db_event_to_pydantic(db_event)
    decision = AgentDecision(
        intervention=db_processed.decision_intervention or "",
        reasoning=db_processed.decision_reasoning or "",
        confidence=db_processed.decision_confidence or 0.0,
        action_taken=db_processed.decision_action_taken or ""
    )
    return ProcessedEvent(
        event=event,
        decision=decision,
        final_status=db_processed.final_status,
        recovered_amount=db_processed.recovered_amount
    )

# --- API Endpoints ---

@app.get("/api/dashboard/stats")
def get_stats(db: Session = Depends(get_db)):
    total_events_count = db.query(DBEvent).count()
    processed_count = db.query(DBProcessedEvent).count()
    
    recovered_events = db.query(DBProcessedEvent).filter(DBProcessedEvent.final_status == "recovered").all()
    recovered_count = len(recovered_events)
    total_recovered_amount = sum(p.recovered_amount for p in recovered_events)
    
    # Potential loss is sum of all events
    total_potential_loss = sum(e.amount for e in db.query(DBEvent).all())
    
    recovery_rate = (recovered_count / processed_count * 100) if processed_count > 0 else 0
    
    return {
        "total_events": total_events_count,
        "processed_events": processed_count,
        "recovered_count": recovered_count,
        "total_recovered_amount": total_recovered_amount,
        "recovery_rate_percent": round(recovery_rate, 2),
        "total_potential_loss": total_potential_loss
    }

@app.get("/api/dashboard/processed", response_model=List[ProcessedEvent])
def get_processed(limit: int = 50, db: Session = Depends(get_db)):
    db_processed = db.query(DBProcessedEvent).order_by(DBProcessedEvent.id.desc()).limit(limit).all()
    results = []
    for p in db_processed:
        event = db.query(DBEvent).filter(DBEvent.id == p.event_id).first()
        if event:
            results.append(_map_db_processed_to_pydantic(p, event))
    return results

@app.get("/api/dashboard/queue", response_model=List[Event])
def get_queue(limit: int = 50, db: Session = Depends(get_db)):
    db_events = db.query(DBEvent).filter(DBEvent.status == "pending").order_by(DBEvent.timestamp.desc()).limit(limit).all()
    return [_map_db_event_to_pydantic(e) for e in db_events]

@app.post("/api/engine/process_next", response_model=ProcessedEvent)
def process_next_event(db: Session = Depends(get_db)):
    # Get oldest pending
    db_event = db.query(DBEvent).filter(DBEvent.status == "pending").order_by(DBEvent.timestamp.asc()).first()
    if not db_event:
        raise HTTPException(status_code=404, detail="Queue empty")
        
    pydantic_event = _map_db_event_to_pydantic(db_event)
    
    # Process event via LangGraph agent
    processed_event = master_agent.process_event(pydantic_event)
    
    # Update event status in DB
    db_event.status = processed_event.final_status if processed_event.final_status != "pending_customer_action" else "pending_customer_action"
    
    db_processed = DBProcessedEvent(
        event_id=db_event.id,
        decision_intervention=processed_event.decision.intervention if processed_event.decision else None,
        decision_reasoning=processed_event.decision.reasoning if processed_event.decision else None,
        decision_confidence=processed_event.decision.confidence if processed_event.decision else None,
        decision_action_taken=processed_event.decision.action_taken if processed_event.decision else None,
        final_status=processed_event.final_status,
        recovered_amount=processed_event.recovered_amount
    )
    
    db.add(db_processed)
    db.commit()
    
    return processed_event

@app.post("/api/engine/process_batch")
def process_batch(count: int = 10, db: Session = Depends(get_db)):
    db_events = db.query(DBEvent).filter(DBEvent.status == "pending").order_by(DBEvent.timestamp.asc()).limit(count).all()
    processed_count = 0
    
    for db_event in db_events:
        pydantic_event = _map_db_event_to_pydantic(db_event)
        processed_event = master_agent.process_event(pydantic_event)
        
        db_event.status = processed_event.final_status if processed_event.final_status != "pending_customer_action" else "pending_customer_action"
        
        db_processed = DBProcessedEvent(
            event_id=db_event.id,
            decision_intervention=processed_event.decision.intervention if processed_event.decision else None,
            decision_reasoning=processed_event.decision.reasoning if processed_event.decision else None,
            decision_confidence=processed_event.decision.confidence if processed_event.decision else None,
            decision_action_taken=processed_event.decision.action_taken if processed_event.decision else None,
            final_status=processed_event.final_status,
            recovered_amount=processed_event.recovered_amount
        )
        db.add(db_processed)
        processed_count += 1
        
    db.commit()
    return {"processed": processed_count}

@app.post("/api/engine/reset")
def reset_demo(db: Session = Depends(get_db)):
    seed_database(db, 150)
    return {"status": "reset successful"}

# --- Copilot Interactive Chat Endpoint ---

@app.post("/api/copilot/chat")
def copilot_chat(req: ChatRequest):
    history = [{"role": msg.role, "content": msg.content} for msg in req.history]
    reply = master_agent.ask_copilot(history)
    return {"reply": reply}

# --- Interactive Mock Payment Checkout Page ---

@app.get("/pay/{link_id}", response_class=HTMLResponse)
def get_checkout_page(link_id: str, db: Session = Depends(get_db)):
    pay_link = db.query(DBPaymentLink).filter(DBPaymentLink.id == link_id).first()
    if not pay_link:
        return HTMLResponse(content="<h1>Error: Payment Link Not Found or Expired</h1>", status_code=404)
    
    event = db.query(DBEvent).filter(DBEvent.id == pay_link.event_id).first()
    if not event:
        return HTMLResponse(content="<h1>Error: Transaction Event Not Found</h1>", status_code=404)

    discount_section = ""
    if pay_link.discount_applied > 0:
        discount_section = f"""
        <div class="discount-badge">🎁 Special {pay_link.discount_applied}% Discount Applied</div>
        <div class="price-comparison">
            <span class="original-price">INR {pay_link.original_amount:.2f}</span>
            <span class="discounted-price">INR {pay_link.amount:.2f}</span>
        </div>
        """
    else:
        discount_section = f"""
        <div class="price-comparison">
            <span class="discounted-price">INR {pay_link.amount:.2f}</span>
        </div>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Aegis Secure Recovery Checkout</title>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
        <style>
            :root {{
                --bg-main: #0B0F19;
                --bg-card: rgba(17, 24, 39, 0.7);
                --accent: #8B5CF6;
                --accent-glow: rgba(139, 92, 246, 0.4);
                --text-main: #F3F4F6;
                --text-sec: #9CA3AF;
                --success: #10B981;
            }}
            * {{
                box-sizing: border-box;
                margin: 0;
                padding: 0;
                font-family: 'Outfit', sans-serif;
            }}
            body {{
                background-color: var(--bg-main);
                color: var(--text-main);
                display: flex;
                align-items: center;
                justify-content: center;
                min-height: 100vh;
                padding: 1.5rem;
                overflow: hidden;
            }}
            body::before {{
                content: '';
                position: absolute;
                width: 300px;
                height: 300px;
                border-radius: 50%;
                background: radial-gradient(circle, var(--accent-glow) 0%, transparent 70%);
                top: 10%;
                left: 10%;
                z-index: -1;
            }}
            body::after {{
                content: '';
                position: absolute;
                width: 300px;
                height: 300px;
                border-radius: 50%;
                background: radial-gradient(circle, rgba(16, 185, 129, 0.2) 0%, transparent 70%);
                bottom: 10%;
                right: 10%;
                z-index: -1;
            }}
            .card {{
                background: var(--bg-card);
                border: 1px solid rgba(255, 255, 255, 0.08);
                backdrop-filter: blur(16px);
                border-radius: 24px;
                width: 100%;
                max-width: 450px;
                padding: 2.5rem;
                box-shadow: 0 20px 40px rgba(0,0,0,0.5);
                transition: transform 0.3s ease;
                text-align: center;
            }}
            .logo {{
                font-weight: 800;
                font-size: 1.8rem;
                letter-spacing: 2px;
                background: linear-gradient(135deg, #A78BFA 0%, #8B5CF6 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 0.5rem;
            }}
            .sub {{
                color: var(--text-sec);
                font-size: 0.9rem;
                margin-bottom: 2rem;
            }}
            .invoice-details {{
                background: rgba(255,255,255,0.03);
                border-radius: 16px;
                padding: 1.5rem;
                border: 1px solid rgba(255,255,255,0.05);
                margin-bottom: 2rem;
                text-align: left;
            }}
            .invoice-row {{
                display: flex;
                justify-content: space-between;
                margin-bottom: 0.8rem;
                font-size: 0.95rem;
            }}
            .invoice-row:last-child {{
                margin-bottom: 0;
            }}
            .label {{
                color: var(--text-sec);
            }}
            .value {{
                font-weight: 600;
            }}
            .discount-badge {{
                display: inline-block;
                background: rgba(16, 185, 129, 0.15);
                border: 1px solid rgba(16, 185, 129, 0.3);
                color: var(--success);
                font-size: 0.85rem;
                font-weight: 600;
                padding: 0.4rem 1rem;
                border-radius: 100px;
                margin-bottom: 1rem;
            }}
            .price-comparison {{
                margin-bottom: 2rem;
            }}
            .original-price {{
                color: var(--text-sec);
                text-decoration: line-through;
                font-size: 1.2rem;
                margin-right: 0.8rem;
            }}
            .discounted-price {{
                font-size: 2.2rem;
                font-weight: 800;
                color: var(--text-main);
            }}
            .pay-btn {{
                background: linear-gradient(135deg, #8B5CF6 0%, #6D28D9 100%);
                border: none;
                color: white;
                font-weight: 700;
                padding: 1rem;
                border-radius: 14px;
                width: 100%;
                font-size: 1.1rem;
                cursor: pointer;
                box-shadow: 0 8px 20px rgba(139, 92, 246, 0.3);
                transition: all 0.2s ease;
            }}
            .pay-btn:hover {{
                transform: translateY(-2px);
                box-shadow: 0 12px 25px rgba(139, 92, 246, 0.5);
            }}
            .pay-btn:active {{
                transform: translateY(0);
            }}
            .payment-methods {{
                display: flex;
                justify-content: center;
                gap: 1.5rem;
                margin-top: 1.5rem;
                color: var(--text-sec);
                font-size: 0.8rem;
            }}
            .method {{
                display: flex;
                align-items: center;
                gap: 0.4rem;
            }}
            /* Success State */
            .success-container {{
                display: none;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                animation: fadeIn 0.5s ease forwards;
            }}
            .checkmark {{
                width: 80px;
                height: 80px;
                border-radius: 50%;
                background: rgba(16, 185, 129, 0.1);
                border: 2px solid var(--success);
                display: flex;
                align-items: center;
                justify-content: center;
                color: var(--success);
                font-size: 3rem;
                font-weight: bold;
                margin-bottom: 1.5rem;
                animation: scaleUp 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards;
            }}
            @keyframes fadeIn {{
                from {{ opacity: 0; transform: translateY(10px); }}
                to {{ opacity: 1; transform: translateY(0); }}
            }}
            @keyframes scaleUp {{
                from {{ transform: scale(0.5); opacity: 0; }}
                to {{ transform: scale(1); opacity: 1; }}
            }}
        </style>
    </head>
    <body>
        <div class="card" id="card">
            <!-- Checkout Content -->
            <div id="checkout-view">
                <div class="logo">AEGIS SECURE</div>
                <p class="sub">Revenue Recovery Payment Gateway</p>
                
                {discount_section}

                <div class="invoice-details">
                    <div class="invoice-row">
                        <span class="label">Customer Name</span>
                        <span class="value">{event.customer_name}</span>
                    </div>
                    <div class="invoice-row">
                        <span class="label">Recovery Reference</span>
                        <span class="value">{event.id}</span>
                    </div>
                    <div class="invoice-row">
                        <span class="label">Original Method</span>
                        <span class="value">{event.customer_preferred_payment_method.upper()}</span>
                    </div>
                    <div class="invoice-row">
                        <span class="label">Payment Link Status</span>
                        <span class="value" style="color: var(--accent);">{pay_link.status.upper()}</span>
                    </div>
                </div>

                <button class="pay-btn" id="pay-button" onclick="executePayment()">
                    Authorize & Complete Payment
                </button>

                <div class="payment-methods">
                    <div class="method">🔒 256-bit SSL Secure</div>
                    <div class="method">⚡ Powered by Aegis AI</div>
                </div>
            </div>

            <!-- Success Content -->
            <div class="success-container" id="success-view">
                <div class="checkmark">✓</div>
                <h2>Payment Successful!</h2>
                <p class="sub" style="margin-bottom: 0;">INR {pay_link.amount:.2f} has been recovered successfully.</p>
                <p style="font-size: 0.85rem; color: var(--text-sec); margin-top: 1rem;">This window can now be closed.</p>
            </div>
        </div>

        <script>
            async function executePayment() {{
                const payButton = document.getElementById('pay-button');
                payButton.innerText = "Processing Transaction...";
                payButton.disabled = true;
                
                try {{
                    const response = await fetch('/api/pay/{link_id}/complete', {{
                        method: 'POST'
                    }});
                    
                    if (response.ok) {{
                        document.getElementById('checkout-view').style.display = 'none';
                        document.getElementById('success-view').style.display = 'flex';
                    }} else {{
                        alert("Payment authorization failed. Please try again.");
                        payButton.innerText = "Authorize & Complete Payment";
                        payButton.disabled = false;
                    }}
                }} catch (error) {{
                    console.error("Error executing payment:", error);
                    alert("Network error. Please check your internet connection.");
                    payButton.innerText = "Authorize & Complete Payment";
                    payButton.disabled = false;
                }}
            }}
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.post("/api/pay/{link_id}/complete")
def complete_payment(link_id: str, db: Session = Depends(get_db)):
    pay_link = db.query(DBPaymentLink).filter(DBPaymentLink.id == link_id).first()
    if not pay_link:
        raise HTTPException(status_code=404, detail="Payment link not found")
        
    if pay_link.status == "paid":
        return {"status": "already_paid"}
        
    # Mark payment link as paid
    pay_link.status = "paid"
    
    # Mark original event as recovered
    event = db.query(DBEvent).filter(DBEvent.id == pay_link.event_id).first()
    if event:
        event.status = "recovered"
        
        # Update ProcessedEvent if it exists, otherwise create it
        processed = db.query(DBProcessedEvent).filter(DBProcessedEvent.event_id == event.id).first()
        if processed:
            processed.final_status = "recovered"
            processed.recovered_amount = pay_link.amount
            processed.decision_action_taken = f"Payment recovered via secure discount link ({pay_link.discount_applied}% off)"
        else:
            processed = DBProcessedEvent(
                event_id=event.id,
                decision_intervention="generate_discount_link_tool",
                decision_reasoning="Manual payment link click/checkout recovery.",
                decision_confidence=1.0,
                decision_action_taken=f"Payment recovered via secure discount link ({pay_link.discount_applied}% off)",
                final_status="recovered",
                recovered_amount=pay_link.amount
            )
            db.add(processed)
            
    db.commit()
    return {"status": "success"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
