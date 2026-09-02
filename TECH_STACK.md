# 🛠️ Tech Stack & Technology Roles

Aegis AI is built using a modern, scalable, and highly responsive technology stack designed to process data autonomously and provide real-time insights.

## Frontend (User Interface & Dashboard)
- **React (via Vite)**: Powers the entire single-page application. Used for its component-based architecture which makes building the complex Live Event Feed and Dashboard stats maintainable.
- **Vanilla CSS (with CSS Variables)**: We specifically avoided utility frameworks like Tailwind to craft a highly custom, premium "Midnight Cyber-Neon" aesthetic utilizing glassmorphism, dynamic glowing borders, and smooth micro-animations.
- **Lucide React**: Provides the clean, scalable SVG icons used throughout the dashboard to represent different event types (failed payments, abandoned carts, invoices).

## Backend (API & Orchestration)
- **FastAPI (Python)**: The core API framework. Chosen for its native asynchronous capabilities and automatic Swagger UI generation. It acts as the high-speed data router between the frontend and the AI agents.
- **Pydantic**: Enforces strict data validation for all incoming and outgoing data, ensuring that the AI never processes malformed event objects.
- **SQLAlchemy**: The Object-Relational Mapper (ORM) used to abstract database operations. It securely manages persistence without writing raw SQL.
- **PostgreSQL**: A robust relational database. Used to permanently store raw events and the resulting agent decisions, creating a reliable audit trail of all AI actions.

## Artificial Intelligence (The Brain)
- **Groq**: The ultra-fast AI inference engine. Used to execute large language models with near-zero latency, which is critical for real-time transaction processing.
- **Llama 3 (70B & 8B)**: The specific Open-Source Large Language Models invoked via Groq. They act as the "reasoning engine" for the agents.
- **LangGraph**: Orchestrates our agentic workflows. Instead of single-turn LLM calls, we implement two stateful Graphs:
  1. **Recovery Graph**: Triages payment errors, dynamically binds and triggers tools based on customer profiles, and updates the database state.
  2. **Copilot Graph**: Powers our conversational chatbot, enabling merchants to query metrics and interactively invoke recovery tools in real-time.
- **Native Tool Calling**: Used by both the Recovery and Copilot graphs to execute Python functions (like updating risk scores, database queries, and generating payment links).
