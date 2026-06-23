from typing import List, Dict, Any, Generator, Tuple
import json
import time
from sqlalchemy import text
from sqlalchemy.orm import Session
import google.generativeai as genai
from openai import OpenAI

from app.core.config import settings
from app.models import ChatMessage, DocumentChunk, Document, Trace
from app.services.ingest import get_chroma_collection, generate_embeddings

def rewrite_query(chat_history: List[Dict[str, str]], query: str, provider: str, api_key: str) -> str:
    """
    Agentic Rewriter: Rewrites a conversational query based on chat history to make it standalone.
    """
    if not chat_history:
        return query

    # Format chat history for the prompt
    history_str = ""
    for msg in chat_history[-6:]:  # Last 3 turns
        role = "User" if msg["role"] == "user" else "Assistant"
        history_str += f"{role}: {msg['content']}\n"

    prompt = f"""Given the following conversation history and a new follow-up question, rewrite the follow-up question to be a standalone search query. 
The standalone query should contain all necessary context from the conversation history so it can be used to search documents.
Do NOT answer the question. Just output the rewritten standalone query.

Conversation History:
{history_str}
Follow-up Question: {query}

Standalone Query:"""

    try:
        if provider == "gemini":
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(settings.GEMINI_LLM_MODEL)
            response = model.generate_content(prompt)
            return response.text.strip()
        elif provider == "openai":
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=settings.OPENAI_LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0
            )
            return response.choices[0].message.content.strip()
    except Exception:
        # Fallback to original query in case of API failure
        return query

def search_sqlite_fts(db: Session, query: str, user_id: int, limit: int = 15) -> List[Dict[str, Any]]:
    """
    Keyword Search using SQLite FTS5.
    """
    # Clean query for FTS5 syntax
    words = [w.strip() for w in query.replace('"', '').replace("'", "").replace("-", " ").split() if w.strip()]
    if not words:
        return []
    
    # We can join words with OR to make it broad and let ranking handle it
    fts_query = " OR ".join([f'"{w}"' for w in words])
    
    sql = text("""
        SELECT dc.id, dc.content, dc.page_number, d.filename, d.id as document_id
        FROM document_chunks dc
        JOIN document_chunks_fts fts ON dc.id = fts.chunk_id
        JOIN documents d ON d.id = dc.document_id
        WHERE d.user_id = :user_id AND document_chunks_fts MATCH :query
        LIMIT :limit
    """)
    
    try:
        results = db.execute(sql, {"user_id": user_id, "query": fts_query, "limit": limit}).fetchall()
        return [
            {
                "id": r.id,
                "content": r.content,
                "page_number": r.page_number,
                "filename": r.filename,
                "document_id": r.document_id
            }
            for r in results
        ]
    except Exception as e:
        print(f"SQLite FTS search error: {e}")
        return []

def search_chroma(db: Session, query: str, user_id: int, provider: str, api_key: str, limit: int = 15) -> List[Dict[str, Any]]:
    """
    Semantic Search using ChromaDB.
    """
    try:
        # Embed query
        query_embeddings = generate_embeddings([query], provider, api_key)
        if not query_embeddings:
            return []
        
        collection = get_chroma_collection(provider, api_key)
        
        # Query ChromaDB with user_id metadata filter
        results = collection.query(
            query_embeddings=query_embeddings,
            n_results=limit,
            where={"user_id": user_id}
        )
        
        if not results or not results["metadatas"] or not results["metadatas"][0]:
            return []
        
        chunks = []
        # chroma returns list of lists
        metadatas = results["metadatas"][0]
        documents = results["documents"][0]
        
        for meta, doc_text in zip(metadatas, documents):
            chunks.append({
                "id": int(meta["chunk_id"]),
                "content": doc_text,
                "page_number": int(meta["page_number"]),
                "filename": meta["filename"],
                "document_id": int(meta["document_id"])
            })
        return chunks
    except Exception as e:
        print(f"ChromaDB search error: {e}")
        return []

def reciprocal_rank_fusion(
    vector_results: List[Dict[str, Any]], 
    keyword_results: List[Dict[str, Any]], 
    k: int = 60,
    top_n: int = 6
) -> List[Dict[str, Any]]:
    """
    Combines search results from vector and keyword search using Reciprocal Rank Fusion (RRF).
    """
    rrf_scores = {}
    chunk_map = {}

    # Helper to calculate RRF score
    def add_ranks(results):
        for rank, item in enumerate(results):
            cid = item["id"]
            chunk_map[cid] = item
            if cid not in rrf_scores:
                rrf_scores[cid] = 0.0
            rrf_scores[cid] += 1.0 / (k + (rank + 1))

    add_ranks(vector_results)
    add_ranks(keyword_results)

    # Sort chunks by fused score
    sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
    return [chunk_map[cid] for cid in sorted_ids[:top_n]]

def get_hybrid_context(
    db: Session, 
    query: str, 
    user_id: int, 
    provider: str, 
    api_key: str, 
    top_n: int = 6
) -> List[Dict[str, Any]]:
    """
    Hybrid Search Pipeline combining ChromaDB + SQLite FTS5 via RRF.
    """
    vector_res = search_chroma(db, query, user_id, provider, api_key, limit=15)
    keyword_res = search_sqlite_fts(db, query, user_id, limit=15)
    return reciprocal_rank_fusion(vector_res, keyword_res, top_n=top_n)

def is_greeting_or_general(query: str) -> bool:
    q = query.lower().strip().replace("?", "").replace("!", "").replace(".", "")
    greetings = {"hi", "hello", "hey", "hola", "greetings", "good morning", "good afternoon", "good evening", "howdy"}
    if q in greetings:
        return True
    if q in {"who are you", "what is this", "help", "what can you do", "get started"}:
        return True
    return False

def answer_query_stream(
    db: Session,
    session_id: str,
    query: str,
    chat_history: List[Dict[str, str]],
    user_id: int,
    provider: str,
    api_key: str
) -> Generator[str, None, None]:
    """
    Executes the complete history-aware RAG pipeline and yields stream tokens.
    Logs trace details to SQLite for observability.
    """
    start_time = time.time()
    
    # Check if the query is a simple greeting
    if is_greeting_or_general(query):
        welcome_text = "Hello! I am your AI Research Assistant. I have successfully chunked and embedded your documents. You can ask me questions about their contents, request summaries, or ask for analysis (such as evaluating a resume or comparing papers). How can I help you today?"
        for token in welcome_text.split(" "):
            yield json.dumps({"type": "token", "text": token + " "})
            time.sleep(0.01)
        yield json.dumps({"type": "citations", "citations": []})
        return

    # 1. Condense/Rewrite user query
    condensed_query = rewrite_query(chat_history, query, provider, api_key)
    
    # 2. Retrieve hybrid context
    context_chunks = get_hybrid_context(db, condensed_query, user_id, provider, api_key)
    
    # Format context for prompt
    context_text = ""
    for idx, chunk in enumerate(context_chunks):
        # We assign a reference index [c1], [c2], etc.
        context_text += f"--- [Document Reference Index: {idx + 1}] ---\n"
        context_text += f"Source Document: {chunk['filename']}\n"
        context_text += f"Page: {chunk['page_number']}\n"
        context_text += f"Content: {chunk['content']}\n\n"

    # Assemble system instructions & RAG prompt
    system_prompt = """You are an advanced AI Research Assistant. Your task is to answer the user's question accurately using the provided document context references.

Rules:
1. Ground your answer strictly in the provided document references. If the query asks for a summary, analysis, review, or evaluation of the documents (like rating or reviewing a resume), perform it thoroughly and helper-fully using the details in the documents.
2. If the query is completely unrelated to the documents or if there is no context available, state: "I cannot find the answer in the uploaded documents."
3. Do not make up facts or assume external information.
4. For every fact you state that is derived from the context, cite the document reference index inline using brackets, e.g., "The candidate has 3 years of experience in Python [1]." 
5. If facts are from multiple references, list them, e.g., "[1, 3]".
6. Provide a clear, professional, and well-structured markdown response.
"""

    user_prompt = f"""Document context references:
{context_text}

User Query: {query}
(Context-optimized query search term: {condensed_query})

Answer:"""

    full_response = ""
    token_count_guess = 0

    try:
        if provider == "gemini":
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(
                settings.GEMINI_LLM_MODEL,
                system_instruction=system_prompt
            )
            # Use streaming
            response_stream = model.generate_content(user_prompt, stream=True)
            for chunk in response_stream:
                token_text = chunk.text
                full_response += token_text
                # Simple approximation: 1 token = 4 characters
                token_count_guess += len(token_text) // 4
                yield json.dumps({"type": "token", "text": token_text})
                
        elif provider == "openai":
            client = OpenAI(api_key=api_key)
            # OpenAI system prompt is passed in messages list
            response_stream = client.chat.completions.create(
                model=settings.OPENAI_LLM_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                stream=True
            )
            for chunk in response_stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    token_text = chunk.choices[0].delta.content
                    full_response += token_text
                    token_count_guess += len(token_text) // 4
                    yield json.dumps({"type": "token", "text": token_text})

        # Calculate exact citation source files mapping
        citations = []
        for idx, chunk in enumerate(context_chunks):
            ref_str = f"[{idx + 1}]"
            # If the LLM referenced this chunk index, map it to output citations
            if ref_str in full_response:
                citations.append({
                    "ref_index": idx + 1,
                    "filename": chunk["filename"],
                    "page_number": chunk["page_number"],
                    "excerpt": chunk["content"][:200] + "..." if len(chunk["content"]) > 200 else chunk["content"]
                })
        
        # Yield metadata at the end of the stream
        yield json.dumps({"type": "citations", "citations": citations})
        
        # Save trace database entry
        latency_ms = (time.time() - start_time) * 1000
        trace = Trace(
            user_id=user_id,
            session_id=session_id,
            query=query,
            condensed_query=condensed_query,
            response=full_response,
            latency_ms=latency_ms,
            total_tokens=token_count_guess + len(system_prompt + user_prompt) // 4
        )
        db.add(trace)
        db.commit()
        
    except Exception as e:
        error_msg = f"\nError in LLM Generation: {str(e)}"
        yield json.dumps({"type": "error", "text": error_msg})
