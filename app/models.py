from datetime import datetime, timezone
import json
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, Text
from sqlalchemy.orm import relationship
from app.core.database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="user", cascade="all, delete-orphan")
    traces = relationship("Trace", back_populates="user", cascade="all, delete-orphan")

class Session(Base):
    __tablename__ = "sessions"
    
    id = Column(String, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    user = relationship("User", back_populates="sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    role = Column(String, nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    citations_raw = Column(Text, nullable=True)  # JSON-encoded list of dicts
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    session = relationship("Session", back_populates="messages")
    
    @property
    def citations(self):
        if self.citations_raw:
            try:
                return json.loads(self.citations_raw)
            except Exception:
                return []
        return []
        
    @citations.setter
    def citations(self, value):
        self.citations_raw = json.dumps(value) if value else None

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String, nullable=False)
    filepath = Column(String, nullable=False)
    file_type = Column(String, nullable=False)  # "pdf", "docx", "txt"
    size_bytes = Column(Integer, nullable=False)
    upload_date = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    user = relationship("User", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")

class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    page_number = Column(Integer, nullable=True)  # 1-indexed page number
    content = Column(Text, nullable=False)
    
    document = relationship("Document", back_populates="chunks")

class Trace(Base):
    __tablename__ = "traces"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_id = Column(String, nullable=True)
    query = Column(Text, nullable=False)
    condensed_query = Column(Text, nullable=True)
    response = Column(Text, nullable=True)
    latency_ms = Column(Float, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    faithfulness_score = Column(Float, nullable=True)  # LLM-as-a-judge score (0-1)
    relevance_score = Column(Float, nullable=True)      # LLM-as-a-judge score (0-1)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    user = relationship("User", back_populates="traces")
