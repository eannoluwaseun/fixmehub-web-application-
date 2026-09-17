# FixMe Hub CRM Web V1

Browser-based rebuild of the FixMe Hub CRM desktop application.

Includes login, dashboard, customers, repair jobs, inventory, sales, expenses and audit log. Uses PostgreSQL (Supabase) in production and SQLite locally. Responsive for PC, tablet and phone. Includes Docker and Render deployment files.

Environment variables: DATABASE_URL, JWT_SECRET, ADMIN_USER, ADMIN_PASSWORD.

Local: `pip install -r requirements.txt` then `uvicorn app.main:app --reload` and open http://127.0.0.1:8000
