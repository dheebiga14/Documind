import os
import shutil
from typing import Optional

from fastapi import (
    FastAPI,
    UploadFile,
    File,
    HTTPException,
    Query
)

from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel

from database import (
    init_database,
    add_document,
    add_chunk,
    get_documents,
    get_document_by_id,
    get_document_chunks,
    update_document_metadata,
    delete_document
)

from document_processor import (
    extract_text,
    split_text
)

from semantic_search import (
    create_embedding,
    semantic_search
)

from document_intelligence import (
    categorize_and_tag,
    create_relevant_snippet,
    generate_concise_answer,
    generate_document_summary
)


# --------------------------------------------------
# CREATE APP
# --------------------------------------------------

app = FastAPI(
    title="DocuMind AI",
    description="AI-Enabled Document Management and Semantic Search System",
    version="2.0"
)


# --------------------------------------------------
# CORS
# --------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


# --------------------------------------------------
# DIRECTORIES
# --------------------------------------------------

UPLOAD_FOLDER = "uploads"

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)


# --------------------------------------------------
# DATABASE & STARTUP BACKFILL
# --------------------------------------------------

init_database()


@app.on_event("startup")
def startup_backfill():
    """
    Ensure existing documents in the database have their categories and tags populated.
    """
    try:
        init_database()
        docs = get_documents()
        for doc in docs:
            # If document has default 'Other' or empty tags, attempt auto-categorization
            if doc["category"] == "Other" or not doc["tags"]:
                chunks = get_document_chunks(doc["id"])
                if chunks:
                    full_text = " ".join(c["text"] for c in chunks)
                    cat, tags = categorize_and_tag(full_text)
                    update_document_metadata(doc["id"], cat, tags)
    except Exception as e:
        print("Startup backfill warning:", e)


# --------------------------------------------------
# REQUEST MODELS
# --------------------------------------------------

class SearchRequest(BaseModel):
    query: str
    limit: Optional[int] = 5
    threshold: Optional[float] = 0.30


class AskRequest(BaseModel):
    question: str
    threshold: Optional[float] = 0.35


# --------------------------------------------------
# HOME
# --------------------------------------------------

@app.get("/")
def home():
    return {
        "message": "DocuMind AI Backend is running",
        "status": "online",
        "version": "2.0"
    }


# --------------------------------------------------
# UPLOAD DOCUMENT
# --------------------------------------------------

@app.post("/api/upload")
async def upload_document(
    file: UploadFile = File(...)
):
    try:
        filename = file.filename

        if not filename:
            raise HTTPException(
                status_code=400,
                detail="Invalid filename"
            )

        extension = os.path.splitext(filename)[1].lower()

        allowed_extensions = [
            ".pdf",
            ".docx",
            ".txt"
        ]

        if extension not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail="Only PDF, DOCX and TXT files are supported"
            )

        # --------------------------------------------------
        # SAVE FILE
        # --------------------------------------------------

        safe_filename = os.path.basename(filename)
        file_path = os.path.join(UPLOAD_FOLDER, safe_filename)

        base_name = os.path.splitext(safe_filename)[0]
        file_extension = os.path.splitext(safe_filename)[1]

        counter = 1
        while os.path.exists(file_path):
            safe_filename = f"{base_name}_{counter}{file_extension}"
            file_path = os.path.join(UPLOAD_FOLDER, safe_filename)
            counter += 1

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        file_size = os.path.getsize(file_path)

        # --------------------------------------------------
        # EXTRACT TEXT
        # --------------------------------------------------

        pages = extract_text(file_path, extension)

        if not pages:
            raise HTTPException(
                status_code=400,
                detail="No readable text found in document"
            )

        # Full text for auto-categorization and tagging
        full_text = " ".join(p["text"] for p in pages)
        category, tags = categorize_and_tag(full_text)

        # --------------------------------------------------
        # ADD DOCUMENT TO DATABASE
        # --------------------------------------------------

        document_id = add_document(
            safe_filename,
            extension.replace(".", "").upper(),
            file_size,
            category=category,
            tags=tags
        )

        # --------------------------------------------------
        # CREATE CHUNKS + EMBEDDINGS
        # --------------------------------------------------

        total_chunks = 0

        for page_data in pages:
            page_number = page_data["page"]
            page_text = page_data["text"]

            chunks = split_text(page_text)

            for chunk in chunks:
                embedding = create_embedding(chunk)
                add_chunk(
                    document_id,
                    page_number,
                    chunk,
                    embedding
                )
                total_chunks += 1

        return {
            "message": "Document uploaded successfully",
            "document_id": document_id,
            "filename": safe_filename,
            "chunks": total_chunks,
            "category": category,
            "tags": tags
        }

    except HTTPException:
        raise

    except Exception as e:
        print("UPLOAD ERROR:", e)
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# --------------------------------------------------
# GET DOCUMENTS (WITH OPTIONAL CATEGORY FILTER)
# --------------------------------------------------

@app.get("/api/documents")
def documents(
    category: Optional[str] = Query(None, description="Filter by category")
):
    docs = get_documents(category=category)
    return docs


# --------------------------------------------------
# GET DOCUMENT SUMMARY
# --------------------------------------------------

@app.get("/api/documents/{document_id}/summary")
def document_summary(document_id: int):
    doc = get_document_by_id(document_id)
    if not doc:
        raise HTTPException(
            status_code=404,
            detail="Document not found"
        )

    chunks = get_document_chunks(document_id)
    summary_data = generate_document_summary(doc, chunks)
    return summary_data


# --------------------------------------------------
# DELETE DOCUMENT
# --------------------------------------------------

@app.delete("/api/documents/{document_id}")
def remove_document(document_id: int):
    deleted = delete_document(document_id)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Document not found"
        )

    return {
        "message": "Document deleted successfully"
    }


# --------------------------------------------------
# IMPROVED SEMANTIC SEARCH
# --------------------------------------------------

@app.post("/api/search")
def search(request: SearchRequest):
    query = request.query.strip()

    if not query:
        return {"results": []}

    # Fetch top raw candidates
    results = semantic_search(query, limit=12)

    # Filter by similarity threshold to hide weak matches
    threshold = request.threshold if request.threshold is not None else 0.30
    filtered_results = [r for r in results if r["similarity"] >= threshold]

    # Limit to the most relevant 3-5 results
    limit = max(3, min(request.limit or 5, 5))
    top_results = filtered_results[:limit]

    formatted_results = []
    for result in top_results:
        formatted_results.append({
            "filename": result["filename"],
            "page": result["page"],
            "similarity": round(result["similarity"] * 100, 2),
            "snippet": create_relevant_snippet(result["text"], query),
            "text": result["text"]  # Complete content for "View More"
        })

    return {
        "results": formatted_results,
        "total_matches": len(formatted_results)
    }


# --------------------------------------------------
# CONCISE AI ANSWERS & MISSING KNOWLEDGE DETECTION
# --------------------------------------------------

@app.post("/api/ask")
def ask_ai(request: AskRequest):
    question = request.question.strip()

    if not question:
        return {
            "knowledge_found": False,
            "title": "Question Required",
            "message": "Please enter a question to ask the AI assistant.",
            "best_score": 0.0,
            "threshold": 35.0,
            "suggestion": "Type or speak a question about your uploaded documents.",
            "answer": "Please enter a question.",
            "sources": []
        }

    # Retrieve candidate chunks
    results = semantic_search(question, limit=8)

    threshold = request.threshold if request.threshold is not None else 0.35

    # Generate concise answer & check missing knowledge
    response_data = generate_concise_answer(question, results, threshold=threshold)

    return response_data


# --------------------------------------------------
# SERVER STATUS
# --------------------------------------------------

@app.get("/api/status")
@app.get("/api/health")
def status():
    return {
        "system": "DocuMind AI",
        "version": "2.0",
        "status": "online",
        "semantic_search": "enabled",
        "document_management": "enabled",
        "document_intelligence": "enabled",
        "voice_support": "enabled"
    }