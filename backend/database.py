import sqlite3

DB_NAME = "cms.db"

    
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Added campus column here
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS printers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            ip TEXT UNIQUE NOT NULL,
            brand TEXT DEFAULT 'Generic',
            oid TEXT DEFAULT '1.3.6.1.2.1.43.10.2.1.4.1.1',
            last_counter INTEGER DEFAULT 0,
            campus TEXT DEFAULT 'TK',
            purchase_date TEXT DEFAULT ''
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')
    
    # Default PIN setup (default: 1234)
    cursor.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('pin', '0228')")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
