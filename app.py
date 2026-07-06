import os
import time

import psycopg2
from psycopg2 import OperationalError
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

DB_HOST = os.environ.get("DB_HOST", "db")
DB_NAME = os.environ.get("DB_NAME", "calculator")
DB_USER = os.environ.get("DB_USER", "calc_user")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "calc_password")
DB_PORT = os.environ.get("DB_PORT", "5432")
DISABLE_DB = os.environ.get("DISABLE_DB", "false").lower() == "true"

# Tracks whether the DB is known to be reachable, so we don't retry a slow
# connection on every single request once we already know it's down.
DB_AVAILABLE = False


def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        port=DB_PORT,
        connect_timeout=3,  # fail fast instead of hanging for a long time
    )


def wait_for_db(retries=5, delay=1):
    """Retry connecting to Postgres a few times (useful on container startup)."""
    global DB_AVAILABLE
    if DISABLE_DB:
        print("DISABLE_DB is set — skipping database connection entirely.")
        DB_AVAILABLE = False
        return False
 
    for attempt in range(1, retries + 1):
        try:
            conn = get_connection()
            conn.close()
            DB_AVAILABLE = True
            return True
        except OperationalError:
            print(f"Database not ready yet (attempt {attempt}/{retries}), retrying in {delay}s...")
            time.sleep(delay)
    DB_AVAILABLE = False
    return False
 
 
def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS calculations (
            id SERIAL PRIMARY KEY,
            expression TEXT NOT NULL,
            result TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );
        """
    )
    conn.commit()
    cur.close()
    conn.close()
 
 
def save_calculation(expression, result):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO calculations (expression, result) VALUES (%s, %s)",
        (expression, str(result)),
    )
    conn.commit()
    cur.close()
    conn.close()
 
 
def get_history(limit=10):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT expression, result, created_at FROM calculations ORDER BY id DESC LIMIT %s",
        (limit,),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows
 
 
def safe_eval(expression):
    """
    Evaluate a basic arithmetic expression safely.
    Only allows numbers and + - * / ( ) . operators — no names, no builtins.
    """
    allowed_chars = set("0123456789.+-*/() ")
    if not expression or not set(expression) <= allowed_chars:
        raise ValueError("Invalid characters in expression")
 
    code = compile(expression, "<calculator>", "eval")
    for name in code.co_names:
        raise ValueError(f"Use of names not allowed: {name}")
 
    return eval(code, {"__builtins__": {}}, {})
 
 
@app.route("/")
def index():
    history = []
    if DB_AVAILABLE:
        try:
            history = get_history()
        except OperationalError:
            pass
    return render_template("index.html", history=history)
 
 
@app.route("/calculate", methods=["POST"])
def calculate():
    data = request.get_json(silent=True) or {}
    expression = data.get("expression", "").strip()
 
    if not expression:
        return jsonify({"error": "No expression provided"}), 400
 
    try:
        result = safe_eval(expression)
    except ZeroDivisionError:
        return jsonify({"error": "Division by zero"}), 400
    except Exception:
        return jsonify({"error": "Invalid expression"}), 400
 
    if DB_AVAILABLE:
        try:
            save_calculation(expression, result)
        except OperationalError:
            pass
 
    return jsonify({"expression": expression, "result": result})

 
@app.route("/history")
def history():
    rows = []
    if DB_AVAILABLE:
        try:
            rows = get_history()
        except OperationalError:
            rows = []
    return jsonify(
        [
            {"expression": r[0], "result": r[1], "created_at": r[2].isoformat()}
            for r in rows
        ]
    )
 
 
if __name__ == "__main__":
    if wait_for_db():
        init_db()
    else:
        print("Warning: could not connect to database, starting app without history support.")
    # use_reloader=False avoids running wait_for_db() twice on startup
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
