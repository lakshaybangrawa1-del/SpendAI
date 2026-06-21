import sqlite3
import os

DB_NAME = "spendai.db"

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    current_dir = os.path.dirname(__file__)
    schema_path = os.path.join(current_dir, 'schema.sql')
    
    with open(schema_path, 'r') as f:
        sql_script = f.read()
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.executescript(sql_script)
    conn.commit()
    conn.close()
    print("✨ Database and Tables initialized successfully!")

def add_expense(amount, category, description, date, source='Manual'):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO expenses (amount, category, description, date, source)
        VALUES (?, ?, ?, ?, ?)
    ''', (amount, category, description, date, source))
    conn.commit()
    conn.close()

def get_all_expenses():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM expenses ORDER BY date DESC')
    rows = cursor.fetchall()
    conn.close()
    return rows

if __name__ == "__main__":
    init_db()