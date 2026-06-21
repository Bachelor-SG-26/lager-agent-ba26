import uuid
from datetime import datetime

from database.database import db_connection


def create_chat_session(thread_id=None):
    """Legt eine Chat-Session an und gibt ihre Thread-ID zurück."""
    thread_id = thread_id or str(uuid.uuid4())
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with db_connection(commit=True) as (_, cursor):
        cursor.execute("""
            INSERT OR IGNORE INTO chat_sessions (thread_id, titel, erstellt_am)
            VALUES (?, ?, ?)
        """, (thread_id, "Neues Gespräch", created_at))

    return thread_id


def get_latest_chat_session():
    """Lädt die zuletzt erstellte Chat-Session."""
    with db_connection() as (_, cursor):
        cursor.execute("""
            SELECT thread_id, titel, erstellt_am
            FROM chat_sessions
            ORDER BY id DESC
            LIMIT 1
        """)
        session = cursor.fetchone()
    return dict(session) if session else None


def list_chat_sessions(limit=10):
    """Lädt die letzten Chat-Sessions für eine einfache Verlaufsauswahl."""
    with db_connection() as (_, cursor):
        cursor.execute("""
            SELECT thread_id, titel, erstellt_am
            FROM chat_sessions
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]


def save_chat_message(thread_id, role, content):
    """Speichert eine einzelne Chat-Nachricht."""
    create_chat_session(thread_id)
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with db_connection(commit=True) as (_, cursor):
        cursor.execute("""
            INSERT INTO chat_nachrichten (thread_id, role, content, erstellt_am)
            VALUES (?, ?, ?, ?)
        """, (thread_id, role, content, created_at))


def load_chat_messages(thread_id):
    """Lädt alle Nachrichten einer Chat-Session in chronologischer Reihenfolge."""
    with db_connection() as (_, cursor):
        cursor.execute("""
            SELECT role, content, erstellt_am
            FROM chat_nachrichten
            WHERE thread_id = ?
            ORDER BY id ASC
        """, (thread_id,))
        return [dict(row) for row in cursor.fetchall()]


def update_chat_title_from_message(thread_id, message):
    """Setzt den Session-Titel aus der ersten Nutzernachricht."""
    title = " ".join((message or "").split())[:48] or "Neues Gespräch"
    with db_connection(commit=True) as (_, cursor):
        cursor.execute("""
            UPDATE chat_sessions
            SET titel = ?
            WHERE thread_id = ? AND titel = 'Neues Gespräch'
        """, (title, thread_id))
