# 🛡️ Aegis: AI Revenue Control Center (Track 03)

**Aegis** is an autonomous, agentic AI platform designed to detect revenue at risk, understand the context of the leakage, and execute bounded recovery workflows. It goes beyond simple static retry rules to dynamically recover payments, checkouts, and invoices.

This project was built for the **Razorpay Hackathon - Track 03 (Revenue Recovery)** by fusing multiple advanced AI concepts into a single unified architecture.

---

## 🌟 What I Built & Why It Wins

Instead of building disparate tools for different problems (a retry tool, a cart reminder tool, a debt chaser tool), we built a **LangGraph-based Master Agentic Graph** that orchestrates specialized sub-agents. 

When revenue leakage occurs, Aegis doesn't just ask *"What failed?"* It asks, *"Who is this customer, why did it fail, and what is the safest intervention to get the money back?"*

### The 3 Core Pillars (Sub-Agents)
1. **The Payment Doctor:** Diagnoses underlying bank/network/fund issues, handles OTP failures, gateway downtimes, and international card declines. Determines if a payment should be retried, routed to a backup gateway, or whitelisted.
2. **The Checkout Rescue Agent:** Analyzes abandoned carts. If a high-value customer drops off due to price sensitivity, unsupported currencies, or payment failure, it dynamically authorizes a targeted recovery discount, alternative currencies routing, or split payment installments.
3. **The Promise-to-Pay Agent (B2B):** Monitors overdue receivables and initiates contextual, interactive conversations (e.g., WhatsApp chasers) based on the client's past payment behavior and risk profile. Routes pricing disputes immediately to human account managers.

---

## 🏗️ Technical Architecture

### 1. Backend (FastAPI / Python)
The backend acts as the brain and data simulator for the application. 
- **Persistent Database:** Implements a scalable **PostgreSQL** database (with automatic local **SQLite fallback**), housing `events`, `processed_events`, `communication_logs` (tracking Whatsapp/email sends), and `payment_links` (tracking discounted checkout tokens).
- **LangGraph Agent Orchestration:** Utilizes **LangGraph** to build stateful multi-node graphs for payment recovery and the merchant assistant. The agent ingests real-time context and uses **Native Tool Calling** to execute database queries, send messages, and generate payment links.
- **Interactive Gateway Simulator:** Exposes a secure checkout endpoint (`/pay/{link_id}`) serving a custom HTML payment gateway. Customers can complete payments here, dynamically updating the PostgreSQL audit logs and the merchant dashboard in real-time.

### 2. Frontend (React / Vite)
The frontend acts as the **Revenue Control Center**.
- **Aesthetic:** We opted for a premium "Midnight Cyber-Neon" design using Vanilla CSS and glassmorphism. It is built to look like an enterprise-grade financial dashboard.
- **Interactive Copilot Chat Widget:** Features a sidebar chat interface where merchants can query metrics ("Show stats"), list failures, or trigger manual interventions ("Route through Gateway B" or "Offer split installments").
- **Live Feed & Simulation:** Features a real-time event ticker showing AI decisions. If the AI generates a recovery payment link, a CTA button appears allowing you to simulate the customer's click, complete the transaction, and watch stats update live.

---

## 🧠 The AI Workflow (How it works under the hood)

When an event hits the system, the workflow is as follows:

```mermaid
graph TD
    A[Failure Event Ingestion] --> B[LangGraph Triage Node]
    B --> C[LLM Diagnostic Node]
    C -- Decides Tool Call --> D[Execute Recovery Tools]
    D -- Route Failover --> D1[route_alternative_gateway_tool]
    D -- Installments --> D2[trigger_split_payment_offer_tool]
    D -- Whitelist Guide --> D3[send_card_whitelist_guide_tool]
    D -- Retries / Discounts --> D4[schedule_smart_retry_tool / generate_discount_link_tool]
    D --> E[Log Communications & Create Payment Links]
    E --> F[Respond Node & Update Database]
```

### Example Recovery Playbook
- **Technical gateway outage:** The agent routes the transaction through `route_alternative_gateway_tool` to backup Gateway B.
- **Credit Limit Exceeded / High-Value Insufficient Funds (>8k INR):** The agent triggers `trigger_split_payment_offer_tool` to offer the customer a 3-part interest-free installment plan.
- **International Card Blocked:** The agent fires `send_card_whitelist_guide_tool` to email whitelisting steps.
- **Incorrect OTP:** The agent suggests an instant UPI scanning bypass link via WhatsApp.

---

## 🚀 How to Run the Project Locally

The project is split into two directories: `backend` and `frontend`.

### Start the Backend

First, set up your Environment Variables:
1. Navigate to the `backend` folder.
2. Ensure you have a PostgreSQL database named `aegis` running locally, or create one in pgAdmin.
3. Add your Groq API key and Postgres URL to the `.env` file: 
   ```env
   GROQ_API_KEY="your_api_key_here"
   DATABASE_URL="postgresql://postgres:password@localhost:5432/aegis"
   ```
   *(Note: If Postgres is not running, the backend automatically falls back to an SQLite `aegis.db` file so it runs out-of-the-box!)*

Then run the backend:
```powershell
cd backend
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt
uvicorn main:app --reload
```
*The backend will run on `http://127.0.0.1:8000`*

### Start the Frontend
```powershell
cd frontend
npm install
npm run dev
```
*The frontend will run on `http://localhost:5173`*

---

## 🎬 How to Demo to the Judges

1. Open the UI at `http://localhost:5173`.
2. Draw their attention to the **"At Risk Revenue"** metric. Explain that this represents the raw queue of failed payments and abandoned carts.
3. Click the **"Start Autonomous Mode"** button.
4. Watch the Live Intervention Feed populate. You will see complex failures like `incorrect_otp`, `credit_limit_exceeded`, `gateway_downtime`, and `international_card_blocked`.
5. Point out the **`⚡ Open Checkout (Simulate Customer Click)`** buttons appearing on the feed. Click one! It opens a gorgeous payment gateway. Complete the payment to show how the **"Successfully Recovered"** revenue instantly updates on the dashboard.
6. Open the **Aegis Copilot** chat panel on the right. Ask it: `"Show recovery stats"` or click **Installment Plan**. Show how the LLM queries the database and gives conversational answers!
