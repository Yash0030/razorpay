# 🛡️ The Solution: Aegis AI Revenue Recovery

## Simple Overview
Aegis is an intelligent, autonomous agent that sits on top of your payment gateway. Whenever a payment fails, a cart is abandoned, or an invoice goes unpaid, Aegis intercepts the event. 

Instead of just following a blind rule (like "wait 1 day and send an email"), Aegis uses a powerful AI brain (Llama 3 via Groq) to look at the specific customer and the exact reason for the failure. It then chooses the perfect "tool" to fix the problem—whether that is silently retrying the card when the bank is back online, texting the customer a backup UPI link, or offering a targeted 5% discount to save a $5,000 abandoned cart. 

It does this instantly, automatically, and at scale.

---

## How the Application Works
1. **The Dashboard**: You open the sleek web interface to see real-time metrics of money at risk versus money successfully recovered.
2. **The Queue**: Synthetic failure events (simulating real-world transaction data) pile up in a pending queue in the PostgreSQL database.
3. **The LangGraph Recovery Agent**: The AI Agent pulls an event from the queue, triages it, binds appropriate tools, and executes them. It generates logs and actions (such as smart gateway retries, communications, or discount links).
4. **Interactive Copilot Chat**: Merchants can talk to the Aegis Assistant directly to query metrics ("What is my recovery rate?"), list transaction failures ("Which payments failed recently?"), or manually trigger actions ("Apply a 10% discount for Aarav").
5. **Interactive Payment Simulator**: If the agent sends a recovery discount link, the merchant can click the link in the live feed to open an interactive mock gateway payment page, authorize the payment, and see the recovered revenue immediately reflect in the dashboard totals in real-time.

---

## 🛠️ Smart Recovery Playbook (Failure Scenarios & Counters)

Aegis is equipped to handle complex real-world payment edge cases through intelligent, conditional actions:

*   **Gateway Downtimes (`gateway_downtime`)**: Automatically detects when the primary processor is unresponsive and routes payments through a secondary gateway, sending a backup checkout link to the user.
*   **Credit Declines (`credit_limit_exceeded` / `insufficient_funds` > 8k INR)**: Recognizes card spending capacity issues on high-ticket purchases and generates a flexible 3-part interest-free installment checkout plan.
*   **Authentication Issues (`incorrect_otp`)**: Identifies customer friction during SMS OTP entry and sends a direct WhatsApp fallback option containing an instant UPI payment scanner bypass.
*   **International Blocks (`international_card_blocked`)**: Flags card declines due to country restrictions and automatically emails a guide showing how to whitelist online/intl transactions in their banking app.
*   **Currency Incompatibility (`unsupported_currency`)**: Auto-routes foreign carts through alternative payment networks supporting localized FX exchange.
*   **Invoice Disputes (`disputed_invoice`)**: Suspends automated collection communications and escalates the ticket directly to the merchant's customer success account manager for manual resolution.

---

## 🚀 How to Run the Application Locally

The project is split into a **Frontend** (React) and a **Backend** (FastAPI + PostgreSQL).

### Step 1: Database Setup
1. Ensure you have **PostgreSQL** installed and running on your machine (e.g., via pgAdmin).
2. Create a new, empty database named `aegis`.

### Step 2: Backend Setup
1. Open a terminal and navigate to the `backend` folder:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On Mac/Linux:
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure Environment Variables:
   - Create a file named `.env` inside the `backend` folder (or rename `.env.example`).
   - Add your API keys and database URL:
     ```env
     GROQ_API_KEY="your_groq_api_key_here"
     DATABASE_URL="postgresql://postgres:password@localhost:5432/aegis"
     ```
     *(Note: Update the `postgres:password` part to match your local PostgreSQL credentials).*
5. Run the backend server:
   ```bash
   uvicorn main:app --reload
   ```

### Step 3: Frontend Setup
1. Open a *new* terminal window and navigate to the `frontend` folder:
   ```bash
   cd frontend
   ```
2. Install the Node modules:
   ```bash
   npm install
   ```
3. Start the development server:
   ```bash
   npm run dev
   ```
4. Open your browser and navigate to the URL provided (usually `http://localhost:5173`) to view the dashboard!
