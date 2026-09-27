import sqlite3
import json

DATABASE = "documents.db"


def get_connection():
    return sqlite3.connect(DATABASE)


def init_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            file_type TEXT,
            file_size INTEGER,
            category TEXT DEFAULT 'Other',
            tags TEXT DEFAULT '[]'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER,
            page INTEGER,
            text TEXT,
            embedding BLOB
        )
    """)

    # Check for existing table schema migrations
    cursor.execute("PRAGMA table_info(documents)")
    columns = [row[1] for row in cursor.fetchall()]

    if "category" not in columns:
        cursor.execute("ALTER TABLE documents ADD COLUMN category TEXT DEFAULT 'Other'")

    if "tags" not in columns:
        cursor.execute("ALTER TABLE documents ADD COLUMN tags TEXT DEFAULT '[]'")

    conn.commit()
    conn.close()


def add_document(filename, file_type, file_size, category="Other", tags="[]"):
    conn = get_connection()
    cursor = conn.cursor()

    if isinstance(tags, (list, tuple)):
        tags_str = json.dumps(tags)
    else:
        tags_str = tags if tags else "[]"

    cursor.execute("""
        INSERT INTO documents
        (filename, file_type, file_size, category, tags)
        VALUES (?, ?, ?, ?, ?)
    """, (filename, file_type, file_size, category, tags_str))

    document_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return document_id


def update_document_metadata(document_id, category, tags):
    conn = get_connection()
    cursor = conn.cursor()

    if isinstance(tags, (list, tuple)):
        tags_str = json.dumps(tags)
    else:
        tags_str = tags if tags else "[]"

    cursor.execute("""
        UPDATE documents
        SET category = ?, tags = ?
        WHERE id = ?
    """, (category, tags_str, document_id))

    conn.commit()
    conn.close()


def add_chunk(document_id, page, text, embedding):
    conn = get_connection()
    cursor = conn.cursor()

    embedding_bytes = embedding.tobytes()

    cursor.execute("""
        INSERT INTO chunks
        (document_id, page, text, embedding)
        VALUES (?, ?, ?, ?)
    """, (
        document_id,
        page,
        text,
        embedding_bytes
    ))

    conn.commit()
    conn.close()


def parse_tags(tags_value):
    if not tags_value:
        return []
    if isinstance(tags_value, list):
        return tags_value
    try:
        parsed = json.loads(tags_value)
        if isinstance(parsed, list):
            return parsed
    except Exception:
        pass
    # Fallback to comma-separated
    return [t.strip() for t in tags_value.split(",") if t.strip()]


def get_documents(category=None):
    conn = get_connection()
    cursor = conn.cursor()

    if category and category.lower() != "all" and category.lower() != "all categories":
        cursor.execute("""
            SELECT id, filename, file_type, file_size, category, tags
            FROM documents
            WHERE LOWER(category) = LOWER(?)
            ORDER BY id DESC
        """, (category,))
    else:
        cursor.execute("""
            SELECT id, filename, file_type, file_size, category, tags
            FROM documents
            ORDER BY id DESC
        """)

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": row[0],
            "filename": row[1],
            "file_type": row[2],
            "file_size": row[3],
            "category": row[4] if row[4] else "Other",
            "tags": parse_tags(row[5])
        }
        for row in rows
    ]


def get_document_by_id(document_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, filename, file_type, file_size, category, tags
        FROM documents
        WHERE id = ?
    """, (document_id,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "id": row[0],
        "filename": row[1],
        "file_type": row[2],
        "file_size": row[3],
        "category": row[4] if row[4] else "Other",
        "tags": parse_tags(row[5])
    }


def get_document_chunks(document_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT page, text
        FROM chunks
        WHERE document_id = ?
        ORDER BY page ASC, id ASC
    """, (document_id,))

    rows = cursor.fetchall()
    conn.close()

    return [{"page": row[0], "text": row[1]} for row in rows]


def delete_document(document_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM chunks WHERE document_id = ?",
        (document_id,)
    )

    cursor.execute(
        "DELETE FROM documents WHERE id = ?",
        (document_id,)
    )

    deleted = cursor.rowcount > 0

    conn.commit()
    conn.close()

    return deleted