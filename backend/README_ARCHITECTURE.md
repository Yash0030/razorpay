# Aegis AI Revenue Recovery - Architecture Upgrade

The backend has been completely overhauled to meet production-level scalability, reliability, and utilize real LLM reasoning.

## Key Changes:

1. **Real LLM Agent Engine (`backend/agents.py`)**
   - Integrated `groq` with the **Llama 3 8B** model.
   - The `MasterAgent` now constructs a precise prompt using live event context (customer risk, preferred method, failure reason) and natively uses **Groq Tool Calling (Function Calling)** to execute recovery actions.
   - The LLM acts as the decision engine to select the best tool (e.g., `send_whatsapp_message`, `schedule_smart_retry`), justify the reasoning via function arguments, and determine the exact action to take.
   - **Reliability:** Built-in fallback to mock agents if the API key is missing or if the API rate limits/errors out.

2. **Scalable Database Architecture (`backend/database.py`)**
   - Removed the unstable in-memory `DB` lists.
   - Implemented a **PostgreSQL** database using `SQLAlchemy` (and `psycopg2-binary`). 
   - Created `DBEvent` and `DBProcessedEvent` schemas for rigid persistence.
   - Automatically seeds the database on initial boot for a seamless demo experience.

3. **Separation of Concerns (`backend/models.py`)**
   - Decoupled `Pydantic` data models into `models.py`.
   - This keeps `main.py` clean and ensures schemas are reusable across endpoints, database mappers, and agents.

4. **Robust Endpoints (`backend/main.py`)**
   - All FastAPI routes were migrated to use SQLAlchemy's dependency injection (`Depends(get_db)`).
   - Added robust querying and mapping functions to convert database schemas to API DTOs.

## Next Steps
To run the LLM, you must add your Groq API Key.
1. Open the `.env` file in the `backend` folder.
2. Set `GROQ_API_KEY="your-api-key"`.
3. Restart your backend server.
