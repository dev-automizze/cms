import secrets
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from apscheduler.schedulers.background import BackgroundScheduler
import sqlite3
from datetime import datetime
from database import init_db, DB_NAME
from snmp_helper import get_printer_counter

app = FastAPI(title="CMS API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()

# --- AUTO-UPGRADE DATABASE SCHEMA ---
def upgrade_schema():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    try:
        c.execute("ALTER TABLE printers ADD COLUMN last_updated TEXT DEFAULT 'Never'")
    except sqlite3.OperationalError:
        pass 
    try:
        c.execute("ALTER TABLE printers ADD COLUMN purchase_date TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass 
    conn.commit()
    conn.close()

upgrade_schema()

# Models
class PrinterReq(BaseModel):
    name: str
    ip: str
    brand: str = "Generic"
    oid: str = "1.3.6.1.2.1.43.10.2.1.4.1.1"
    campus: str = "TK" 
    purchase_date: str = ""

class AuthReq(BaseModel):
    pin: str

# --- BACKGROUND SCHEDULER (Every 10 Mins) ---
def scheduled_counter_scan():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, ip, oid FROM printers")
    printers = c.fetchall()
    
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    for pid, ip, oid in printers:
        count = get_printer_counter(ip, oid)
        if count != -1:
            c.execute("UPDATE printers SET last_counter = ?, last_updated = ? WHERE id = ?", (count, now_str, pid))
            
    conn.commit()
    conn.close()

scheduler = BackgroundScheduler()
scheduler.add_job(scheduled_counter_scan, 'interval', minutes=10)
scheduler.start()

# --- API ENDPOINTS ---

@app.post("/api/verify-pin")
def verify_pin(auth: AuthReq):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute("SELECT value FROM config WHERE key='pin'")
        row = c.fetchone()
        db_pin = row[0] if row else "1234"
    except Exception:
        db_pin = "1234"
    finally:
        conn.close()
    
    if auth.pin == db_pin:
        return {"status": "ok"}
    raise HTTPException(status_code=401, detail="Invalid PIN")

@app.get("/api/printers")
def get_printers():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, name, ip, brand, oid, last_counter, campus, last_updated, purchase_date FROM printers")
    rows = c.fetchall()
    conn.close()
    
    return [
    {"id": r[0], "name": r[1], "ip": r[2], "brand": r[3], "oid": r[4], "last_counter": r[5], "campus": r[6], "last_updated": r[7], "purchase_date": r[8]}
    for r in rows
    ]

@app.post("/api/printers")
def add_printer(p: PrinterReq):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO printers (name, ip, brand, oid, campus, purchase_date) VALUES (?, ?, ?, ?, ?, ?)",
          (p.name, p.ip, p.brand, p.oid, p.campus, p.purchase_date))
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="IP address already exists")
    finally:
        conn.close()
    return {"status": "created"}

@app.put("/api/printers/{printer_id}")
def update_printer(printer_id: int, p: PrinterReq):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE printers SET name=?, ip=?, brand=?, oid=?, campus=?, purchase_date=? WHERE id=?",
          (p.name, p.ip, p.brand, p.oid, p.campus, p.purchase_date, printer_id))
    conn.commit()
    conn.close()
    return {"status": "updated"}

@app.delete("/api/printers/{printer_id}")
def delete_printer(printer_id: int):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM printers WHERE id=?", (printer_id,))
    conn.commit()
    conn.close()
    return {"status": "deleted"}

@app.get("/api/counters/scan")
def scan_all_counters():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, ip, oid, last_counter FROM printers")
    printers = c.fetchall()
    
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    results = []
    
    for pid, ip, oid, last_count in printers:
        count = get_printer_counter(ip, oid)
        if count != -1:
            c.execute("UPDATE printers SET last_counter = ?, last_updated = ? WHERE id = ?", (count, now_str, pid))
            results.append({"id": pid, "ip": ip, "counter": count, "status": "online"})
        else:
            results.append({"id": pid, "ip": ip, "counter": last_count, "status": "offline"})
            
    conn.commit()
    conn.close()
    return {"results": results}

# --- GOOGLE SETTINGS ENDPOINTS ---

@app.get("/api/settings/google-webhook")
def get_webhook():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    result = c.execute("SELECT value FROM settings WHERE key='google_webhook'").fetchone()
    conn.close()
    return {"url": result[0] if result else ""}

@app.post("/api/settings/google-webhook")
async def save_webhook(req: Request):
    data = await req.json()
    url = data.get("url")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    if url:
        c.execute(
            "INSERT INTO settings (key, value) VALUES ('google_webhook', ?) ON CONFLICT(key) DO UPDATE SET value=?",
            (url, url)
        )
    else:
        c.execute("DELETE FROM settings WHERE key='google_webhook'")
        
    conn.commit()
    conn.close()
    return {"status": "saved"}

# --- API KEY & EXPORT ENDPOINTS ---
@app.get("/api/settings/api-key")
def get_api_key():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    row = c.execute("SELECT value FROM settings WHERE key='api_key'").fetchone()
    
    if not row:
        # Generate a secure 22-character URL-safe string
        new_key = secrets.token_urlsafe(16)
        c.execute("INSERT INTO settings (key, value) VALUES ('api_key', ?)", (new_key,))
        conn.commit()
        api_key = new_key
    else:
        api_key = row[0]
        
    conn.close()
    return {"api_key": api_key}

@app.post("/api/settings/api-key/regenerate")
def regenerate_api_key():
    new_key = secrets.token_urlsafe(16)
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO settings (key, value) VALUES ('api_key', ?) ON CONFLICT(key) DO UPDATE SET value=?", (new_key, new_key))
    conn.commit()
    conn.close()
    return {"api_key": new_key}

@app.get("/api/export/printers")
def export_printers(api_key: str = None):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    row = c.execute("SELECT value FROM settings WHERE key='api_key'").fetchone()
    valid_key = row[0] if row else None
    
    # Check if the key matches
    if not valid_key or api_key != valid_key:
        conn.close()
        raise HTTPException(status_code=401, detail="Invalid or missing API Key")
        
    c.execute("SELECT id, name, ip, brand, oid, last_counter, campus, last_updated FROM printers")
    rows = c.fetchall()
    conn.close()
    
    # Return data in a format ready for Google Sheets
    return [
        {"id": r[0], "name": r[1], "ip": r[2], "brand": r[3], "oid": r[4], "last_counter": r[5], "campus": r[6], "last_updated": r[7]}
        for r in rows
    ]

# Adjust the 'directory' path if your dist folder is located somewhere else relative to main.py
app.mount("/", StaticFiles(directory="../frontend/dist", html=True), name="static")
