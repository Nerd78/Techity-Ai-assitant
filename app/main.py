import os
import time
import json
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
import shutil

from app.core.config import settings
from app.core.database import Base, engine, get_db
from app.core.security import get_password_hash, verify_password, create_access_token, decode_access_token
from app.models import User, Session as ChatSession, ChatMessage, Document, Trace
from app.services.ingest import process_and_ingest_file, delete_document_from_indexes
from app.services.rag import answer_query_stream, get_hybrid_context
from app.services.eval import evaluate_and_update_trace

# Create database tables and SQLite FTS5 index on startup
Base.metadata.create_all(bind=engine)
with engine.connect() as conn:
    conn.execute(text("CREATE VIRTUAL TABLE IF NOT EXISTS document_chunks_fts USING fts5(chunk_id UNINDEXED, content);"))
    conn.commit()

app = FastAPI(title=settings.PROJECT_NAME)

# CORS middleware config
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Authentication Dependency
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)) -> User:
    token = credentials.credentials
    username = decode_access_token(token)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user

# ----------------- Auth Routes -----------------

@app.post("/v1/auth/signup")
def signup(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.username == username).first()
    if db_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")
    
    hashed = get_password_hash(password)
    new_user = User(username=username, hashed_password=hashed)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    token = create_access_token(subject=username)
    return {"access_token": token, "token_type": "bearer", "username": username}

@app.post("/v1/auth/login")
def login(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(subject=username)
    return {"access_token": token, "token_type": "bearer", "username": username}

@app.get("/v1/auth/me")
def get_me(user: User = Depends(get_current_user)):
    return {"id": user.id, "username": user.username}

# ----------------- Document Routes -----------------

@app.post("/v1/ingest")
async def ingest_file(
    file: UploadFile = File(...),
    provider: str = Form(...),
    api_key: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Ensure data storage folder exists
    data_dir = "./data"
    os.makedirs(data_dir, exist_ok=True)
    
    # Save the file locally
    file_id = str(time.time()).replace(".", "")
    safe_filename = f"{file_id}_{file.filename}"
    temp_path = os.path.join(data_dir, safe_filename)
    
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    size_bytes = os.path.getsize(temp_path)
    file_type = file.filename.split(".")[-1].lower()
    
    if file_type not in ["pdf", "docx", "txt"]:
        os.remove(temp_path)
        raise HTTPException(status_code=400, detail="Only PDF, DOCX, and TXT files are supported")
        
    try:
        doc = process_and_ingest_file(
            db=db,
            file_path=temp_path,
            filename=file.filename,
            file_type=file_type,
            size_bytes=size_bytes,
            user_id=user.id,
            provider=provider,
            api_key=api_key
        )
        return {
            "id": doc.id,
            "filename": doc.filename,
            "size_bytes": doc.size_bytes,
            "upload_date": doc.upload_date.isoformat()
        }
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(status_code=500, detail=f"Failed to process document: {str(e)}")

@app.get("/v1/documents")
def list_documents(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    docs = db.query(Document).filter(Document.user_id == user.id).all()
    return [
        {
            "id": d.id,
            "filename": d.filename,
            "file_type": d.file_type,
            "size_bytes": d.size_bytes,
            "upload_date": d.upload_date.isoformat()
        }
        for d in docs
    ]

@app.delete("/v1/documents/{document_id}")
def delete_document(
    document_id: int, 
    provider: str,
    api_key: str,
    user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == user.id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    try:
        # Delete from local file system
        if os.path.exists(doc.filepath):
            os.remove(doc.filepath)
        # Delete indexes and DB records
        delete_document_from_indexes(db, doc, provider, api_key)
        return {"status": "success", "message": "Document deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete document indices: {str(e)}")

# ----------------- Session Routes -----------------

@app.post("/v1/sessions")
def create_session(title: str = Form(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session_id = str(uuid_generator())
    db_session = ChatSession(id=session_id, user_id=user.id, title=title)
    db.add(db_session)
    db.commit()
    return {"id": db_session.id, "title": db_session.title, "created_at": db_session.created_at.isoformat()}

@app.get("/v1/sessions")
def list_sessions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sessions = db.query(ChatSession).filter(ChatSession.user_id == user.id).order_by(ChatSession.created_at.desc()).all()
    return [{"id": s.id, "title": s.title, "created_at": s.created_at.isoformat()} for s in sessions]

@app.get("/v1/sessions/{session_id}")
def get_session_history(session_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    messages = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.asc()).all()
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "citations": m.citations,
            "created_at": m.created_at.isoformat()
        }
        for m in messages
    ]

@app.delete("/v1/sessions/{session_id}")
def delete_session(session_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    db.delete(session)
    db.commit()
    return {"status": "success", "message": "Session deleted"}

def uuid_generator():
    import uuid
    return uuid.uuid4()

# ----------------- RAG Query Route -----------------

@app.post("/v1/query")
async def run_query(
    background_tasks: BackgroundTasks,
    session_id: str = Form(...),
    query: str = Form(...),
    provider: str = Form(...),
    api_key: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Verify session ownership
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Fetch previous messages for the agentic rewriter
    db_messages = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.asc()).all()
    chat_history = [{"role": m.role, "content": m.content} for m in db_messages]

    # Save user message
    user_msg = ChatMessage(session_id=session_id, role="user", content=query)
    db.add(user_msg)
    db.commit()

    async def stream_wrapper():
        # Yield the client connection token
        full_assistant_reply = ""
        citations_data = []
        
        # We fetch the engine URL for background evals (so it can open its own connection)
        db_url = settings.DATABASE_URL
        
        try:
            # Call generation stream
            stream = answer_query_stream(
                db=db,
                session_id=session_id,
                query=query,
                chat_history=chat_history,
                user_id=user.id,
                provider=provider,
                api_key=api_key
            )
            
            for event_str in stream:
                event = json.loads(event_str)
                if event["type"] == "token":
                    full_assistant_reply += event["text"]
                elif event["type"] == "citations":
                    citations_data = event["citations"]
                yield f"data: {event_str}\n\n"
            
            # Save assistant message in DB once complete
            assistant_msg = ChatMessage(
                session_id=session_id,
                role="assistant",
                content=full_assistant_reply
            )
            assistant_msg.citations = citations_data
            db.add(assistant_msg)
            db.commit()
            
            # Retrieve the trace row we just logged to launch LLM background evaluation
            last_trace = db.query(Trace).filter(
                Trace.session_id == session_id, 
                Trace.user_id == user.id
            ).order_by(Trace.created_at.desc()).first()
            
            if last_trace:
                # Build context snippet for the evaluation judge
                # We query for the hybrid context to pass to the evaluator
                chunks = get_hybrid_context(db, last_trace.condensed_query or query, user.id, provider, api_key)
                context_text = "\n".join([f"[{i+1}] {c['content']}" for i, c in enumerate(chunks)])
                
                # Register background evaluation task
                background_tasks.add_task(
                    evaluate_and_update_trace,
                    query=query,
                    response=full_assistant_reply,
                    context_text=context_text,
                    trace_id=last_trace.id,
                    provider=provider,
                    api_key=api_key,
                    db_url=db_url
                )
                
        except Exception as e:
            err = {"type": "error", "text": f"Stream execution error: {str(e)}"}
            yield f"data: {json.dumps(err)}\n\n"

    return StreamingResponse(stream_wrapper(), media_type="text/event-stream")

# ----------------- Trace & Observability Routes -----------------

@app.get("/v1/traces")
def get_traces(limit: int = 50, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Returns traces logged in SQLite for displaying inside the Observability Dashboard.
    """
    traces = db.query(Trace).filter(Trace.user_id == user.id).order_by(Trace.created_at.desc()).limit(limit).all()
    return [
        {
            "id": t.id,
            "session_id": t.session_id,
            "query": t.query,
            "condensed_query": t.condensed_query,
            "response": t.response[:200] + "..." if t.response and len(t.response) > 200 else t.response,
            "latency_ms": t.latency_ms,
            "total_tokens": t.total_tokens,
            "faithfulness_score": t.faithfulness_score,
            "relevance_score": t.relevance_score,
            "created_at": t.created_at.isoformat()
        }
        for t in traces
    ]

# ----------------- Serve static frontend -----------------
# Ensure the static folder exists
os.makedirs("./static", exist_ok=True)
app.mount("/", StaticFiles(directory="static", html=True), name="static")
