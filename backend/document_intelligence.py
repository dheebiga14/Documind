import re
from collections import Counter
import numpy as np

# We import model and create_embedding from semantic_search so that the model is loaded only once
from semantic_search import model, create_embedding

CATEGORIES = [
    "Artificial Intelligence",
    "Software Engineering",
    "Education",
    "Research",
    "Programming",
    "Business",
    "Other"
]

CATEGORY_PROFILES = {
    "Artificial Intelligence": (
        "artificial intelligence machine learning deep learning neural networks computer vision "
        "natural language processing nlp large language models llm reinforcement learning data science "
        "predictive modeling embeddings transformers algorithm automation"
    ),
    "Software Engineering": (
        "software engineering system architecture agile devops microservices cloud infrastructure "
        "software testing regression testing deployment continuous integration bug tracking "
        "modules components safety critical version control maintenance framework"
    ),
    "Education": (
        "education student teaching school university classroom curriculum course syllabus "
        "academic pedagogy lecture exam learning study student assessment grades instructional"
    ),
    "Research": (
        "research paper study methodology scientific experiment findings literature review "
        "academic journal results analysis hypothesis empirical evaluation survey citations methodology"
    ),
    "Programming": (
        "programming languages python javascript typescript java c++ coding algorithms "
        "data structures syntax functions compilation debugging scripts frontend backend api web development"
    ),
    "Business": (
        "business marketing sales revenue finance investment corporate enterprise leadership "
        "commerce accounting market customer strategy organization management profits economics"
    )
}

STOPWORDS = set(
    "a about above after again against all am an and any are aren't as at be because been before being below "
    "between both but by can cannot could couldn't did didn't do does doesn't doing don't down during each few "
    "for from further had hadn't has hasn't have haven't having he he'd he'll he's her here here's hers herself "
    "him himself his how how's i i'd i'll i'm i've if in into is isn't it it's its itself let's me more most "
    "mustn't my myself no nor not of off on once only or other ought our ours ourselves out over own same shan't "
    "she she'd she'll she's should shouldn't so some such than that that's the their theirs them themselves then "
    "there there's these they they'd they'll they're they've this those through to too under until up very was "
    "wasn't we we'd we'll we're we've were weren't what what's when when's where where's which while who who's "
    "whom why why's with won't would wouldn't you you'd you'll you're you've your yours yourself yourselves "
    "also however therefore using based page report table section parameter result value project summary".split()
)

# Precompute category profile embeddings
_category_embeddings = {
    cat: create_embedding(desc)
    for cat, desc in CATEGORY_PROFILES.items()
}


def categorize_and_tag(text: str):
    """
    Categorizes the document text into one of the predefined categories
    and generates 3-5 relevant tags.
    """
    clean_text = text.strip()
    if not clean_text:
        return "Other", ["document"]

    # Use first 1500 characters + middle sample for representation
    sample_text = clean_text[:2000]
    doc_embedding = create_embedding(sample_text)

    # Compute similarity to category profiles
    best_category = "Other"
    best_sim = 0.0

    for cat, cat_emb in _category_embeddings.items():
        sim = float(
            np.dot(doc_embedding, cat_emb) /
            (np.linalg.norm(doc_embedding) * np.linalg.norm(cat_emb))
        )
        if sim > best_sim:
            best_sim = sim
            best_category = cat

    # Categorization threshold: if below 0.22, default to 'Other'
    if best_sim < 0.22:
        best_category = "Other"

    # Generate 3-5 tags
    tags = extract_tags(clean_text, top_n=5)

    return best_category, tags


def extract_tags(text: str, top_n=5):
    """
    Extracts 3-5 concise, meaningful tags from the document text.
    """
    # Clean words and extract meaningful keywords & bigrams
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text.lower())
    filtered_words = [w for w in words if w not in STOPWORDS and len(w) >= 4 and not w.isdigit()]

    # Extract bigrams
    bigrams = []
    for i in range(len(words) - 1):
        w1, w2 = words[i], words[i + 1]
        if (
            w1 not in STOPWORDS
            and w2 not in STOPWORDS
            and len(w1) >= 3
            and len(w2) >= 3
            and not w1.isdigit()
            and not w2.isdigit()
        ):
            bigrams.append(f"{w1}-{w2}")

    # Count occurrences
    word_counts = Counter(filtered_words)
    bigram_counts = Counter(bigrams)

    # Combine prioritizing informative bigrams and top single words
    candidate_tags = []
    seen = set()

    for phrase, count in bigram_counts.most_common(10):
        if count >= 2:
            candidate_tags.append(phrase)
            seen.update(phrase.split("-"))

    for word, count in word_counts.most_common(15):
        if word not in seen:
            candidate_tags.append(word)
            seen.add(word)

    # Format cleanly
    clean_tags = []
    for tag in candidate_tags:
        clean_tag = tag.replace("_", "-").strip("-")
        if clean_tag and clean_tag not in clean_tags:
            clean_tags.append(clean_tag)
        if len(clean_tags) >= top_n:
            break

    # If fewer than 3, add generic fallbacks
    if len(clean_tags) < 3:
        clean_tags.extend(["document", "analysis", "overview"][: 3 - len(clean_tags)])

    return clean_tags[:top_n]


def create_relevant_snippet(chunk_text: str, query: str, max_chars=180) -> str:
    """
    Finds the most relevant sentence or snippet window in the chunk for the query.
    """
    sentences = split_into_sentences(chunk_text)
    if not sentences:
        return chunk_text[:max_chars].strip() + ("..." if len(chunk_text) > max_chars else "")

    query_words = set(re.findall(r"\w+", query.lower()))
    best_sentence = sentences[0]
    best_score = -1

    for s in sentences:
        s_words = set(re.findall(r"\w+", s.lower()))
        overlap = len(query_words.intersection(s_words))
        if overlap > best_score:
            best_score = overlap
            best_sentence = s

    snippet = best_sentence.strip()
    if len(snippet) > max_chars:
        snippet = snippet[:max_chars].rsplit(" ", 1)[0] + "..."
    return snippet


def split_into_sentences(text: str) -> list:
    """
    Cleanly splits text into sentences while filtering out empty or noise fragments.
    """
    raw_sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    cleaned = []
    for s in raw_sentences:
        clean = s.strip()
        # Remove special bullet characters like \x7f or markdown dashes
        clean = re.sub(r"[\x00-\x1f\x7f]+", " ", clean).strip()
        clean = re.sub(r"^[•\-\*\s]+", "", clean).strip()
        if len(clean) >= 20 and not clean.endswith(":") and len(clean.split()) >= 4:
            cleaned.append(clean)
    return cleaned


def generate_concise_answer(question: str, semantic_results: list, threshold=0.35):
    """
    Generates a concise, direct answer based only on relevant retrieved document content.
    Detects missing knowledge when no content satisfies the similarity threshold.
    """
    if not semantic_results:
        return {
            "knowledge_found": False,
            "title": "Knowledge Not Found",
            "message": "No sufficiently relevant information was found in your uploaded documents.",
            "best_score": 0.0,
            "threshold": round(threshold * 100, 1),
            "suggestion": "Please consider uploading a document covering this topic or try rephrasing your question.",
            "answer": "No sufficiently relevant information was found in your uploaded documents.",
            "sources": []
        }

    # Best relevance score across all results
    best_similarity = max(r["similarity"] for r in semantic_results)

    # Missing knowledge check
    if best_similarity < threshold:
        return {
            "knowledge_found": False,
            "title": "Knowledge Not Found",
            "message": "No sufficiently relevant information was found in your uploaded documents.",
            "best_score": round(best_similarity * 100, 1),
            "threshold": round(threshold * 100, 1),
            "suggestion": "Please consider uploading a document covering this topic or try rephrasing your question.",
            "answer": "No sufficiently relevant information was found in your uploaded documents.",
            "sources": []
        }

    # Filter only relevant results meeting the threshold
    relevant_results = [r for r in semantic_results if r["similarity"] >= threshold]

    # Collect sentences from top relevant chunks
    candidate_sentences = []
    sentence_sources = {}
    q_emb = create_embedding(question)

    for res in relevant_results[:3]:
        sentences = split_into_sentences(res["text"])
        for s in sentences:
            if s not in sentence_sources:
                candidate_sentences.append(s)
                sentence_sources[s] = {
                    "filename": res["filename"],
                    "page": res["page"]
                }

    if not candidate_sentences:
        # Fallback to chunk snippet if sentence splitting was too strict
        top_res = relevant_results[0]
        return {
            "knowledge_found": True,
            "answer": top_res["text"][:300].strip() + "...",
            "best_score": round(best_similarity * 100, 1),
            "sources": [{"filename": top_res["filename"], "page": top_res["page"]}]
        }

    # Score each sentence with sentence embedding similarity to the question
    sentence_embeddings = model.encode(candidate_sentences)
    scored_sentences = []

    for i, s in enumerate(candidate_sentences):
        s_emb = sentence_embeddings[i]
        sim = float(
            np.dot(q_emb, s_emb) /
            (np.linalg.norm(q_emb) * np.linalg.norm(s_emb))
        )
        scored_sentences.append((sim, s))

    scored_sentences.sort(key=lambda x: x[0], reverse=True)

    # Pick top 2-3 distinct, concise sentences
    chosen_sentences = []
    used_sources = []
    seen_texts = set()

    for sim, s in scored_sentences:
        # Avoid near duplicate sentences
        normalized = re.sub(r"\W+", "", s.lower())
        if any(normalized in seen or seen in normalized for seen in seen_texts):
            continue
        seen_texts.add(normalized)
        chosen_sentences.append(s)
        src = sentence_sources[s]
        if src not in used_sources:
            used_sources.append(src)
        if len(chosen_sentences) >= 3:
            break

    # Build concise, structured answer
    if len(chosen_sentences) == 1:
        concise_text = chosen_sentences[0]
    else:
        concise_text = "\n\n".join([f"• {s}" for s in chosen_sentences])

    answer = f"Based on your documents:\n\n{concise_text}"

    return {
        "knowledge_found": True,
        "answer": answer,
        "best_score": round(best_similarity * 100, 1),
        "sources": used_sources
    }


def generate_document_summary(document: dict, chunks: list):
    """
    Generates a structured, concise document summary including overview and key points.
    """
    if not chunks:
        return {
            "filename": document.get("filename", "Unknown"),
            "file_type": document.get("file_type", ""),
            "file_size": document.get("file_size", 0),
            "category": document.get("category", "Other"),
            "tags": document.get("tags", []),
            "pages_count": 0,
            "chunks_count": 0,
            "total_words": 0,
            "overview": "No readable content found in document.",
            "key_points": []
        }

    # Gather all sentences
    all_sentences = []
    total_words = 0
    pages = set()

    for chunk in chunks:
        text = chunk.get("text", "")
        total_words += len(text.split())
        pages.add(chunk.get("page", 1))
        sentences = split_into_sentences(text)
        all_sentences.extend(sentences)

    # Deduplicate sentences while preserving order
    unique_sentences = []
    seen = set()
    for s in all_sentences:
        norm = re.sub(r"\W+", "", s.lower())
        if norm not in seen and len(s) > 25:
            seen.add(norm)
            unique_sentences.append(s)

    if not unique_sentences:
        overview = "Document uploaded successfully with structured text segments."
        key_points = ["Document content processed into indexable chunks."]
    elif len(unique_sentences) <= 3:
        overview = " ".join(unique_sentences)
        key_points = unique_sentences
    else:
        # Use sentence embeddings to find centroid (most central sentences for overview)
        embeddings = model.encode(unique_sentences)
        doc_centroid = np.mean(embeddings, axis=0)

        scored = []
        for i, emb in enumerate(embeddings):
            sim = float(
                np.dot(doc_centroid, emb) /
                (np.linalg.norm(doc_centroid) * np.linalg.norm(emb))
            )
            scored.append((sim, i, unique_sentences[i]))

        # Sort by centrality
        scored.sort(key=lambda x: x[0], reverse=True)

        # Overview from top 2 central sentences (ordered by document appearance)
        top_overview_indices = sorted([item[1] for item in scored[:2]])
        overview = " ".join([unique_sentences[i] for i in top_overview_indices])

        # Key points from top 3-5 distinct informative sentences
        key_point_indices = sorted([item[1] for item in scored[1:5]])
        key_points = [unique_sentences[i] for i in key_point_indices]

    reading_time_min = max(1, round(total_words / 200))

    return {
        "filename": document.get("filename", "Unknown"),
        "file_type": document.get("file_type", ""),
        "file_size": document.get("file_size", 0),
        "category": document.get("category", "Other"),
        "tags": document.get("tags", []),
        "pages_count": len(pages),
        "chunks_count": len(chunks),
        "total_words": total_words,
        "reading_time": f"{reading_time_min} min read",
        "overview": overview,
        "key_points": key_points
    }
