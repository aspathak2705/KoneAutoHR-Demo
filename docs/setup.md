# Setup & Installation Guide

## Backend
1. Initialize virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Initialize and run database migrations:
   ```bash
   alembic upgrade head
   ```
4. Run FastAPI:
   ```bash
   uvicorn main:app --reload
   ```

## Frontend
1. Install dependencies:
   ```bash
   npm install
   ```
2. Run frontend development server:
   ```bash
   npm run dev
   ```
