---
title: Intelli-Credit
emoji: 💳
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
fullWidth: true
---

# Intelli-Credit

This project has been updated to run locally without Docker or `docker-compose`.

## Prerequisites

- Python 3.11+
- Node.js (for frontend/backend)
- Golang (for go-service)
- A local or remote instance of **Neo4j** running on `localhost:7687`
- A local or remote instance of **Qdrant** running on `localhost:6333`

## Running the AI Service Locally

1. Navigate to the `ai-service` folder.
2. Create a virtual environment: `python -m venv venv`
3. Activate the virtual environment:
   - Windows: `.\venv\Scripts\activate`
   - Linux/Mac: `source venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Copy the example environment variables: `cp .env.example .env` and fill in your keys.
6. Start the server:
   ```bash
   uvicorn main:app --reload  --port 8001
   ```
