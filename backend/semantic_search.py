import sqlite3
import numpy as np

from sentence_transformers import SentenceTransformer


model = SentenceTransformer(
    "all-MiniLM-L6-v2"
)


DATABASE = "documents.db"


def create_embedding(text):

    return model.encode(text)


def semantic_search(query, limit=10):

    query_embedding = create_embedding(query)

    conn = sqlite3.connect(DATABASE)

    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            chunks.text,
            chunks.page,
            chunks.embedding,
            documents.filename
        FROM chunks
        JOIN documents
        ON chunks.document_id = documents.id
    """)

    rows = cursor.fetchall()

    conn.close()

    results = []

    for text, page, embedding_bytes, filename in rows:

        embedding = np.frombuffer(
            embedding_bytes,
            dtype=np.float32
        )

        similarity = np.dot(
            query_embedding,
            embedding
        ) / (
            np.linalg.norm(query_embedding)
            * np.linalg.norm(embedding)
        )

        results.append({

            "filename": filename,

            "page": page,

            "text": text,

            "similarity": float(similarity)

        })

    results.sort(
        key=lambda x: x["similarity"],
        reverse=True
    )

    return results[:limit]