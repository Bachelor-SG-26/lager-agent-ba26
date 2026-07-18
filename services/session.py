import json
from datetime import datetime
from database.database import get_connection


def erstelle_session(thread_id):
    """Legt eine neue Chat-Session in der DB an."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO chat_sessions (thread_id, titel, erstellt_am) VALUES (?, ?, ?)",
        (thread_id, "Neues Gespräch", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    conn.close()


def aktualisiere_session_titel(thread_id, erste_nachricht):
    """Setzt den Titel einer Session auf die erste User-Nachricht (gekürzt)."""
    titel = erste_nachricht[:50] + ("..." if len(erste_nachricht) > 50 else "")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE chat_sessions SET titel = ? WHERE thread_id = ? AND titel = 'Neues Gespräch'",
        (titel, thread_id),
    )
    conn.commit()
    conn.close()


def lade_alle_sessions():
    """Gibt alle Sessions zurück, neueste zuerst."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT thread_id, titel, erstellt_am
        FROM chat_sessions
        ORDER BY erstellt_am DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows


def speichere_nachricht(thread_id, role, content, tools_used=None):
    """Speichert eine einzelne Nachricht in der DB."""
    conn = get_connection()
    cursor = conn.cursor()
    tools_str = json.dumps(tools_used, ensure_ascii=False) if tools_used else None
    cursor.execute(
        "INSERT INTO chat_nachrichten (thread_id, role, content, tools_used, erstellt_am) VALUES (?, ?, ?, ?, ?)",
        (thread_id, role, content, tools_str, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    conn.close()


def benenne_session_um(thread_id, neuer_titel):
    """Setzt den Titel einer Session auf einen neuen Wert."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE chat_sessions SET titel = ? WHERE thread_id = ?",
        (neuer_titel, thread_id),
    )
    conn.commit()
    conn.close()


def loesche_session(thread_id):
    """Löscht eine Session und alle zugehörigen Nachrichten."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chat_nachrichten WHERE thread_id = ?", (thread_id,))
    cursor.execute("DELETE FROM chat_sessions WHERE thread_id = ?", (thread_id,))
    conn.commit()
    conn.close()


def lade_letzte_session():
    """Gibt die thread_id der neuesten Session zurück, oder None."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT thread_id FROM chat_sessions
        ORDER BY erstellt_am DESC LIMIT 1
    """)
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def lade_nachrichten(thread_id):
    """Lädt alle Nachrichten einer Session aus der DB."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT role, content, tools_used
        FROM chat_nachrichten
        WHERE thread_id = ?
        ORDER BY id ASC
    """, (thread_id,))
    rows = cursor.fetchall()
    conn.close()

    messages = []
    for role, content, tools_str in rows:
        msg = {"role": role, "content": content}
        if tools_str:
            msg["tools_used"] = json.loads(tools_str)
        messages.append(msg)
    return messages
