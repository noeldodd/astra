# check_and_clean_memory.py
"""
Script to check memory storage format and clean up duplicate Bobs
Run from ~/jarvis directory
"""

import os
import json
from pathlib import Path

# Find where memory is actually stored
state_dir = Path.home() / "jarvis" / "state"
print(f"Checking state directory: {state_dir}")
print(f"Exists: {state_dir.exists()}")

if state_dir.exists():
    print(f"\nContents of {state_dir}:")
    for item in state_dir.iterdir():
        print(f"  {item.name} ({'dir' if item.is_dir() else 'file'})")

# Check for SQLite database
db_path = state_dir / "memory.db"
if db_path.exists():
    print(f"\n✓ Found SQLite database: {db_path}")
    
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Get tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print(f"Tables: {[t[0] for t in tables]}")
    
    # Try to find contacts in any table
    for table_name in [t[0] for t in tables]:
        try:
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 1")
            columns = [desc[0] for desc in cursor.description]
            print(f"\n{table_name} columns: {columns}")
            
            # If it looks like it has contacts
            if 'name' in columns or 'contact' in table_name.lower():
                cursor.execute(f"SELECT * FROM {table_name}")
                rows = cursor.fetchall()
                print(f"  Rows: {len(rows)}")
                if rows:
                    print(f"  Sample: {rows[0]}")
        except Exception as e:
            print(f"  Error reading {table_name}: {e}")
    
    conn.close()

# Check for JSON file storage
memory_dir = state_dir / "memory"
if memory_dir.exists():
    print(f"\n✓ Found memory directory: {memory_dir}")
    for item in memory_dir.iterdir():
        print(f"  {item.name}")
        if item.suffix == '.json':
            with open(item) as f:
                data = json.load(f)
                if isinstance(data, list):
                    print(f"    {len(data)} items")
                    if data:
                        print(f"    Sample: {data[0]}")
                elif isinstance(data, dict):
                    print(f"    Keys: {list(data.keys())}")

# Check contexts directory
contexts_dir = state_dir / "contexts"
if contexts_dir.exists():
    print(f"\n✓ Found contexts directory: {contexts_dir}")
    for item in contexts_dir.iterdir():
        print(f"  {item.name}")

print("\n" + "="*60)
print("To clean up duplicates, we need to know the storage format.")
print("Run this script to see where contacts are stored, then we can")
print("create a cleanup script specific to your storage format.")