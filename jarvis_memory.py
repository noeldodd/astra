# jarvis_memory.py
"""
JARVIS Memory System

Handles persistent storage of:
- Contacts (name, phone, email, etc.)
- Calendar events
- Notes/aides-memoire
- Knowledge base (citations, summaries)
- User preferences

Storage strategy:
- SQLite for structured data (contacts, calendar)
- JSON files for flexible data (notes, knowledge)
- Hybrid approach for performance and flexibility
"""

import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple
import hashlib


class MemoryStore:
    """Main memory storage manager"""
    
    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir
        self.db_path = storage_dir / "memory.db"
        self.notes_dir = storage_dir / "notes"
        self.knowledge_dir = storage_dir / "knowledge"
        
        # Ensure directories exist
        self.notes_dir.mkdir(parents=True, exist_ok=True)
        self.knowledge_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_database()
    
    def _log(self, message: str):
        """Simple logging"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [MEMORY] {message}")
    
    # ==================== DATABASE INITIALIZATION ====================
    
    def _init_database(self):
        """Initialize SQLite database with schema"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Contacts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                name_normalized TEXT NOT NULL,
                phone_home TEXT,
                phone_work TEXT,
                phone_mobile TEXT,
                email_personal TEXT,
                email_work TEXT,
                company TEXT,
                title TEXT,
                address TEXT,
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                metadata TEXT
            )
        """)
        
        # Create index for fast name lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_contacts_name 
            ON contacts(name_normalized)
        """)
        
        # Calendar events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS calendar_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                start_datetime TEXT NOT NULL,
                end_datetime TEXT,
                location TEXT,
                attendees TEXT,
                recurrence TEXT,
                reminder_minutes INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                metadata TEXT
            )
        """)
        
        # Create index for date queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_calendar_start 
            ON calendar_events(start_datetime)
        """)
        
        # User preferences table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # Memory tags (for categorization)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                category TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        
        conn.commit()
        conn.close()
        
        self._log("Database initialized")
    
    def _normalize_name(self, name: str) -> str:
        """Normalize name for searching (lowercase, no extra spaces)"""
        return " ".join(name.lower().split())
    
    def _now(self) -> str:
        """Get current timestamp in ISO format"""
        return datetime.now().isoformat()
    
    # ==================== CONTACTS ====================
    
    def create_contact(
        self,
        name: str,
        phone_home: Optional[str] = None,
        phone_work: Optional[str] = None,
        phone_mobile: Optional[str] = None,
        email_personal: Optional[str] = None,
        email_work: Optional[str] = None,
        company: Optional[str] = None,
        title: Optional[str] = None,
        address: Optional[str] = None,
        notes: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> int:
        """Create a new contact"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = self._now()
        name_normalized = self._normalize_name(name)
        
        cursor.execute("""
            INSERT INTO contacts (
                name, name_normalized, phone_home, phone_work, phone_mobile,
                email_personal, email_work, company, title, address, notes,
                created_at, updated_at, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name, name_normalized, phone_home, phone_work, phone_mobile,
            email_personal, email_work, company, title, address, notes,
            now, now, json.dumps(metadata) if metadata else None
        ))
        
        contact_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        self._log(f"Created contact: {name} (ID: {contact_id})")
        return contact_id
    
    def get_contact(self, contact_id: int) -> Optional[Dict]:
        """Get contact by ID"""
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def find_contacts(self, query: str) -> List[Dict]:
        """Find contacts by name (fuzzy search)"""
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query_normalized = self._normalize_name(query)
        
        # Search with LIKE for flexibility
        cursor.execute("""
            SELECT * FROM contacts 
            WHERE name_normalized LIKE ?
            ORDER BY name
        """, (f"%{query_normalized}%",))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def update_contact(
        self,
        contact_id: int,
        **fields
    ) -> bool:
        """Update contact fields"""
        
        if not fields:
            return False
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Build UPDATE query dynamically
        allowed_fields = {
            'name', 'phone_home', 'phone_work', 'phone_mobile',
            'email_personal', 'email_work', 'company', 'title',
            'address', 'notes', 'metadata'
        }
        
        updates = []
        values = []
        
        for key, value in fields.items():
            if key in allowed_fields:
                if key == 'name':
                    updates.append("name = ?")
                    updates.append("name_normalized = ?")
                    values.append(value)
                    values.append(self._normalize_name(value))
                elif key == 'metadata':
                    updates.append("metadata = ?")
                    values.append(json.dumps(value) if value else None)
                else:
                    updates.append(f"{key} = ?")
                    values.append(value)
        
        if not updates:
            conn.close()
            return False
        
        updates.append("updated_at = ?")
        values.append(self._now())
        values.append(contact_id)
        
        query = f"UPDATE contacts SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, values)
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        if success:
            self._log(f"Updated contact ID {contact_id}")
        
        return success
    
    def delete_contact(self, contact_id: int) -> bool:
        """Delete a contact"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
        success = cursor.rowcount > 0
        
        conn.commit()
        conn.close()
        
        if success:
            self._log(f"Deleted contact ID {contact_id}")
        
        return success
    
    def list_contacts(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """List all contacts"""
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM contacts 
            ORDER BY name 
            LIMIT ? OFFSET ?
        """, (limit, offset))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    # ==================== CALENDAR ====================
    
    def create_event(
        self,
        title: str,
        start_datetime: str,
        end_datetime: Optional[str] = None,
        description: Optional[str] = None,
        location: Optional[str] = None,
        attendees: Optional[List[str]] = None,
        reminder_minutes: Optional[int] = None,
        metadata: Optional[Dict] = None
    ) -> int:
        """Create a calendar event"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = self._now()
        
        cursor.execute("""
            INSERT INTO calendar_events (
                title, description, start_datetime, end_datetime, location,
                attendees, reminder_minutes, created_at, updated_at, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            title, description, start_datetime, end_datetime, location,
            json.dumps(attendees) if attendees else None,
            reminder_minutes, now, now,
            json.dumps(metadata) if metadata else None
        ))
        
        event_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        self._log(f"Created event: {title} (ID: {event_id})")
        return event_id
    
    def get_event(self, event_id: int) -> Optional[Dict]:
        """Get event by ID"""
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM calendar_events WHERE id = ?", (event_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            event = dict(row)
            # Parse JSON fields
            if event.get('attendees'):
                event['attendees'] = json.loads(event['attendees'])
            if event.get('metadata'):
                event['metadata'] = json.loads(event['metadata'])
            return event
        return None
    
    def find_events(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        query: Optional[str] = None
    ) -> List[Dict]:
        """Find events by date range or text search"""
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        conditions = []
        params = []
        
        if start_date:
            conditions.append("start_datetime >= ?")
            params.append(start_date)
        
        if end_date:
            conditions.append("start_datetime <= ?")
            params.append(end_date)
        
        if query:
            conditions.append("(title LIKE ? OR description LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%"])
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        cursor.execute(f"""
            SELECT * FROM calendar_events 
            WHERE {where_clause}
            ORDER BY start_datetime
        """, params)
        
        rows = cursor.fetchall()
        conn.close()
        
        events = []
        for row in rows:
            event = dict(row)
            if event.get('attendees'):
                event['attendees'] = json.loads(event['attendees'])
            if event.get('metadata'):
                event['metadata'] = json.loads(event['metadata'])
            events.append(event)
        
        return events
    
    def update_event(self, event_id: int, **fields) -> bool:
        """Update event fields"""
        
        if not fields:
            return False
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        allowed_fields = {
            'title', 'description', 'start_datetime', 'end_datetime',
            'location', 'attendees', 'reminder_minutes', 'metadata'
        }
        
        updates = []
        values = []
        
        for key, value in fields.items():
            if key in allowed_fields:
                if key in ['attendees', 'metadata']:
                    updates.append(f"{key} = ?")
                    values.append(json.dumps(value) if value else None)
                else:
                    updates.append(f"{key} = ?")
                    values.append(value)
        
        if not updates:
            conn.close()
            return False
        
        updates.append("updated_at = ?")
        values.append(self._now())
        values.append(event_id)
        
        query = f"UPDATE calendar_events SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, values)
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        if success:
            self._log(f"Updated event ID {event_id}")
        
        return success
    
    def delete_event(self, event_id: int) -> bool:
        """Delete an event"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM calendar_events WHERE id = ?", (event_id,))
        success = cursor.rowcount > 0
        
        conn.commit()
        conn.close()
        
        if success:
            self._log(f"Deleted event ID {event_id}")
        
        return success
    
    # ==================== NOTES (Aides-Memoire) ====================
    
    def create_note(
        self,
        title: str,
        content: str,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict] = None
    ) -> str:
        """Create a note/aide-memoire"""
        
        note_id = hashlib.sha256(
            f"{title}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]
        
        note = {
            "id": note_id,
            "title": title,
            "content": content,
            "tags": tags or [],
            "metadata": metadata or {},
            "created_at": self._now(),
            "updated_at": self._now()
        }
        
        note_file = self.notes_dir / f"{note_id}.json"
        with open(note_file, 'w') as f:
            json.dump(note, f, indent=2)
        
        self._log(f"Created note: {title} (ID: {note_id})")
        return note_id
    
    def get_note(self, note_id: str) -> Optional[Dict]:
        """Get note by ID"""
        
        note_file = self.notes_dir / f"{note_id}.json"
        
        if note_file.exists():
            with open(note_file) as f:
                return json.load(f)
        
        return None
    
    def find_notes(
        self,
        query: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> List[Dict]:
        """Find notes by text or tags"""
        
        notes = []
        
        for note_file in self.notes_dir.glob("*.json"):
            try:
                with open(note_file) as f:
                    note = json.load(f)
                
                # Filter by query
                if query:
                    query_lower = query.lower()
                    if query_lower not in note.get("title", "").lower() and \
                       query_lower not in note.get("content", "").lower():
                        continue
                
                # Filter by tags
                if tags:
                    note_tags = set(note.get("tags", []))
                    if not set(tags).intersection(note_tags):
                        continue
                
                notes.append(note)
            except:
                continue
        
        # Sort by updated_at descending
        notes.sort(key=lambda n: n.get("updated_at", ""), reverse=True)
        
        return notes
    
    def update_note(
        self,
        note_id: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict] = None
    ) -> bool:
        """Update a note"""
        
        note = self.get_note(note_id)
        if not note:
            return False
        
        if title is not None:
            note["title"] = title
        if content is not None:
            note["content"] = content
        if tags is not None:
            note["tags"] = tags
        if metadata is not None:
            note["metadata"] = metadata
        
        note["updated_at"] = self._now()
        
        note_file = self.notes_dir / f"{note_id}.json"
        with open(note_file, 'w') as f:
            json.dump(note, f, indent=2)
        
        self._log(f"Updated note ID {note_id}")
        return True
    
    def delete_note(self, note_id: str) -> bool:
        """Delete a note"""
        
        note_file = self.notes_dir / f"{note_id}.json"
        
        if note_file.exists():
            note_file.unlink()
            self._log(f"Deleted note ID {note_id}")
            return True
        
        return False
    
    def list_notes(self, limit: int = 50) -> List[Dict]:
        """List recent notes"""
        
        notes = []
        
        for note_file in self.notes_dir.glob("*.json"):
            try:
                with open(note_file) as f:
                    notes.append(json.load(f))
            except:
                continue
        
        # Sort by updated_at descending
        notes.sort(key=lambda n: n.get("updated_at", ""), reverse=True)
        
        return notes[:limit]
    
    # ==================== PREFERENCES ====================
    
    def set_preference(self, key: str, value: Any) -> bool:
        """Set a user preference"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO preferences (key, value, updated_at)
            VALUES (?, ?, ?)
        """, (key, json.dumps(value), self._now()))
        
        conn.commit()
        conn.close()
        
        self._log(f"Set preference: {key}")
        return True
    
    def get_preference(self, key: str, default: Any = None) -> Any:
        """Get a user preference"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT value FROM preferences WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return json.loads(row[0])
        
        return default
    
    def list_preferences(self) -> Dict[str, Any]:
        """List all preferences"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT key, value FROM preferences")
        rows = cursor.fetchall()
        conn.close()
        
        return {key: json.loads(value) for key, value in rows}
    
    # ==================== STATISTICS ====================
    
    def get_stats(self) -> Dict[str, int]:
        """Get memory storage statistics"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM contacts")
        contacts_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM calendar_events")
        events_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM preferences")
        prefs_count = cursor.fetchone()[0]
        
        conn.close()
        
        notes_count = len(list(self.notes_dir.glob("*.json")))
        
        return {
            "contacts": contacts_count,
            "calendar_events": events_count,
            "notes": notes_count,
            "preferences": prefs_count
        }


# ==================== TESTING ====================

def test_memory_store():
    """Test the memory store"""
    
    from pathlib import Path
    import tempfile
    import shutil
    
    # Create temp directory
    temp_dir = Path(tempfile.mkdtemp())
    
    try:
        print("\n" + "=" * 60)
        print("Testing Memory Store")
        print("=" * 60)
        
        store = MemoryStore(temp_dir)
        
        # Test 1: Create contacts
        print("\n1. Creating contacts...")
        bob_id = store.create_contact(
            name="Bob Smith",
            phone_mobile="555-1212",
            email_personal="bob@email.com",
            company="TechCorp"
        )
        
        sarah_id = store.create_contact(
            name="Sarah Chen",
            phone_work="555-1313",
            email_work="sarah@company.com"
        )
        
        print(f"Created Bob (ID: {bob_id}) and Sarah (ID: {sarah_id})")
        
        # Test 2: Find contacts
        print("\n2. Finding contacts...")
        results = store.find_contacts("bob")
        print(f"Found {len(results)} contact(s) matching 'bob':")
        for contact in results:
            print(f"  - {contact['name']}: {contact['phone_mobile']}")
        
        # Test 3: Update contact
        print("\n3. Updating Bob's email...")
        store.update_contact(bob_id, email_work="bob.smith@work.com")
        bob = store.get_contact(bob_id)
        print(f"Bob's work email: {bob['email_work']}")
        
        # Test 4: Create notes
        print("\n4. Creating notes...")
        note1_id = store.create_note(
            title="Remember meeting",
            content="Don't forget to prepare slides for Monday's presentation",
            tags=["work", "reminder"]
        )
        
        note2_id = store.create_note(
            title="Grocery list",
            content="Milk, eggs, bread, coffee",
            tags=["personal", "shopping"]
        )
        
        print(f"Created 2 notes: {note1_id}, {note2_id}")
        
        # Test 5: Find notes
        print("\n5. Finding notes with 'work' tag...")
        notes = store.find_notes(tags=["work"])
        for note in notes:
            print(f"  - {note['title']}: {note['content'][:50]}...")
        
        # Test 6: Create calendar event
        print("\n6. Creating calendar event...")
        event_id = store.create_event(
            title="Team meeting",
            start_datetime="2025-11-25T14:00:00",
            end_datetime="2025-11-25T15:00:00",
            location="Conference Room A",
            attendees=["Bob Smith", "Sarah Chen"]
        )
        print(f"Created event (ID: {event_id})")
        
        # Test 7: Find events
        print("\n7. Finding events...")
        events = store.find_events(
            start_date="2025-11-25T00:00:00",
            end_date="2025-11-26T00:00:00"
        )
        for event in events:
            print(f"  - {event['title']} at {event['start_datetime']}")
        
        # Test 8: Preferences
        print("\n8. Setting preferences...")
        store.set_preference("favorite_color", "blue")
        store.set_preference("theme", "dark")
        
        color = store.get_preference("favorite_color")
        print(f"Favorite color: {color}")
        
        # Test 9: Statistics
        print("\n9. Statistics...")
        stats = store.get_stats()
        print(f"Contacts: {stats['contacts']}")
        print(f"Events: {stats['calendar_events']}")
        print(f"Notes: {stats['notes']}")
        print(f"Preferences: {stats['preferences']}")
        
        print("\n✅ All tests passed!")
        
    finally:
        # Cleanup
        shutil.rmtree(temp_dir)
        print(f"\nCleaned up temp directory: {temp_dir}")


if __name__ == "__main__":
    """
    Test the memory store
    
    Usage:
        python jarvis_memory.py
    """
    test_memory_store()