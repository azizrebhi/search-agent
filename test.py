# test_connection.py
import psycopg

url = postgresql://postgres:Ag0ZjLgmLbKNCm62@db.qycxlerrecbxohiursuv.supabase.co:5432/postgres

try:
    with psycopg.connect(url) as conn:
        print("✅ Connected successfully to Supabase Postgres!")
except Exception as e:
    print("❌ Connection failed:", e)
