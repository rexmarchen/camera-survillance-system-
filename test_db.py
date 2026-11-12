import os
import sqlite3
import sys

print("Testing CamFu Database Connectivity...")
connected = False

# 1. Try MySQL
try:
    import mysql.connector
    conn = mysql.connector.connect(
        host="localhost",
        port=3306,
        user="root",
        password="Shivam@9797",
        database="camfu_db",
        connection_timeout=2
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, camera_id, motion_score, overall_priority_score, timestamp FROM priority_scores ORDER BY timestamp DESC LIMIT 5")
    rows = cursor.fetchall()
    print(f"[MySQL] Connected successfully! Total sample rows fetched: {len(rows)}")
    for row in rows:
        print(" ", row)
    cursor.close()
    conn.close()
    connected = True
except Exception as e:
    print(f"[MySQL] Not accessible ({e}). Checking SQLite fallback...")

# 2. Try SQLite
if not connected:
    sqlite_path = os.path.abspath("camfu.db")
    if os.path.exists(sqlite_path):
        try:
            conn = sqlite3.connect(sqlite_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT id, camera_id, motion_score, overall_priority_score, timestamp FROM priority_scores ORDER BY id DESC LIMIT 5")
            rows = [dict(r) for r in cursor.fetchall()]
            print(f"[SQLite] Connected to {sqlite_path}! Total sample rows fetched: {len(rows)}")
            for row in rows:
                print(" ", row)
            cursor.close()
            conn.close()
            connected = True
        except Exception as e:
            print(f"[SQLite] Error: {e}")
    else:
        print(f"[SQLite] File not found at {sqlite_path}")

if connected:
    print("\nDatabase verification PASSED.")
else:
    print("\nDatabase verification FAILED.")
