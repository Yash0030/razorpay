import uuid
import random
from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, String, Float, Integer, ForeignKey, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship
import os
from dotenv import load_dotenv

load_dotenv()

# Attempt connection to Postgres, fallback to SQLite if authentication or database missing
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/aegis")
try:
    engine = create_engine(DATABASE_URL)
    # Test connection immediately
    with engine.connect() as conn:
        print("Connected to PostgreSQL database successfully.")
except Exception as e:
    print(f"PostgreSQL connection failed ({e}). Falling back to local SQLite database.")
    DATABASE_URL = "sqlite:///./aegis.db"
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class DBEvent(Base):
    __tablename__ = "events"
    id = Column(String, primary_key=True, index=True)
    type = Column(String)
    amount = Column(Float)
    currency = Column(String, default="INR")
    customer_id = Column(String)
    customer_name = Column(String)
    customer_risk_score = Column(Float)
    customer_total_spent = Column(Float)
    customer_preferred_payment_method = Column(String)
    timestamp = Column(String)
    raw_reason = Column(String)
    status = Column(String, default="pending")
    
    # Relationships
    processed = relationship("DBProcessedEvent", back_populates="event", uselist=False)
    communications = relationship("DBCommunicationLog", back_populates="event")
    payment_links = relationship("DBPaymentLink", back_populates="event")

class DBProcessedEvent(Base):
    __tablename__ = "processed_events"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    event_id = Column(String, ForeignKey("events.id"))
    decision_intervention = Column(String, nullable=True)
    decision_reasoning = Column(String, nullable=True)
    decision_confidence = Column(Float, nullable=True)
    decision_action_taken = Column(String, nullable=True)
    final_status = Column(String)
    recovered_amount = Column(Float)
    
    event = relationship("DBEvent", back_populates="processed")

class DBCommunicationLog(Base):
    __tablename__ = "communication_logs"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    event_id = Column(String, ForeignKey("events.id"))
    channel = Column(String) # "whatsapp" or "email"
    recipient = Column(String)
    subject = Column(String, nullable=True)
    body = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

    event = relationship("DBEvent", back_populates="communications")

class DBPaymentLink(Base):
    __tablename__ = "payment_links"
    id = Column(String, primary_key=True, index=True) # unique payment link token
    event_id = Column(String, ForeignKey("events.id"))
    amount = Column(Float)
    original_amount = Column(Float)
    discount_applied = Column(Integer, default=0)
    status = Column(String, default="active") # "active", "paid", "expired"
    created_at = Column(DateTime, default=datetime.utcnow)

    event = relationship("DBEvent", back_populates="payment_links")

# Safely create all tables
try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"Error creating database tables: {e}")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def seed_database(db: Session, count: int = 150):
    # Clear tables safely (handles both SQLite and Postgres)
    db.query(DBPaymentLink).delete()
    db.query(DBCommunicationLog).delete()
    db.query(DBProcessedEvent).delete()
    db.query(DBEvent).delete()
    db.commit()

    names = ["Aarav", "Vihaan", "Aditya", "Sai", "Arjun", "Zara", "Diya", "Aanya", "Isha", "Riya"]
    event_types = ["payment_failed", "checkout_abandoned", "invoice_overdue"]
    reasons = {
        "payment_failed": [
            "insufficient_funds", 
            "temporary_bank_error", 
            "card_expired", 
            "network_timeout",
            "incorrect_otp",
            "credit_limit_exceeded",
            "gateway_downtime",
            "international_card_blocked"
        ],
        "checkout_abandoned": [
            "payment_page_closed", 
            "high_shipping_cost", 
            "distracted", 
            "method_unavailable",
            "promo_code_failed",
            "unsupported_currency"
        ],
        "invoice_overdue": [
            "forgot", 
            "cashflow_issue", 
            "disputed", 
            "no_response",
            "disputed_invoice",
            "pending_client_approval"
        ]
    }
    
    events = []
    for _ in range(count):
        e_type = random.choices(event_types, weights=[0.6, 0.3, 0.1])[0]
        events.append(
            DBEvent(
                id=f"evt_{uuid.uuid4().hex[:8]}",
                type=e_type,
                amount=round(random.uniform(500, 15000), 2),
                currency="INR",
                customer_id=f"cust_{random.randint(1000, 9999)}",
                customer_name=f"{random.choice(names)} {random.choice(['Patel', 'Sharma', 'Singh', 'Kumar', 'Rao'])}",
                customer_risk_score=round(random.uniform(0.1, 0.9), 2),
                customer_total_spent=round(random.uniform(1000, 50000), 2),
                customer_preferred_payment_method=random.choice(["upi", "card", "netbanking"]),
                timestamp=(datetime.now() - timedelta(minutes=random.randint(1, 10000))).isoformat(),
                raw_reason=random.choice(reasons[e_type]),
                status="pending"
            )
        )
    
    events.sort(key=lambda x: x.timestamp, reverse=True)
    db.add_all(events)
    db.commit()
