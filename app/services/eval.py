from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import google.generativeai as genai
from openai import OpenAI
import re

from app.core.config import settings
from app.models import Trace

def parse_score(llm_output: str) -> float:
    """
    Extracts a floating-point score (0.0 to 1.0) from the LLM judge output.
    """
    cleaned = llm_output.strip()
    match = re.search(r"([0-9\.]+)", cleaned)
    if match:
        try:
            score = float(match.group(1))
            return min(max(score, 0.0), 1.0)
        except ValueError:
            pass
    return 0.5

def judge_faithfulness(query: str, response: str, context: str, provider: str, api_key: str) -> float:
    """
    Evaluates if the response is grounded strictly in the context (no hallucinations).
    """
    prompt = f"""You are an expert AI system evaluation judge. Your task is to rate the FAITHFULNESS of the Answer based strictly on the provided Context.
Faithfulness measures if the Answer contains ONLY facts that are directly mentioned in the Context. If the Answer contains external assumptions, speculation, or unmentioned facts, the score must be lower.

Context:
{context}

Answer to Evaluate:
{response}

Rate the FAITHFULNESS from 0.0 (completely hallucinated/unsupported) to 1.0 (completely faithful/supported).
Provide only the numeric score (e.g., 0.95 or 0.2) as the output. Do not include any reasoning or explanation.

Score:"""
    try:
        if provider == "gemini":
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(settings.GEMINI_LLM_MODEL)
            res = model.generate_content(prompt)
            return parse_score(res.text)
        elif provider == "openai":
            client = OpenAI(api_key=api_key)
            res = client.chat.completions.create(
                model=settings.OPENAI_LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0
            )
            return parse_score(res.choices[0].message.content)
    except Exception as e:
        print(f"Faithfulness judge failed: {e}")
    return 0.8  # fallback default

def judge_relevance(query: str, response: str, provider: str, api_key: str) -> float:
    """
    Evaluates if the response directly addresses the user's question.
    """
    prompt = f"""You are an expert AI system evaluation judge. Your task is to rate the ANSWER RELEVANCE of the Answer to the User Query.
Answer Relevance measures if the Answer directly, clearly, and fully answers the User Query (regardless of whether the information is factually correct).

User Query:
{query}

Answer to Evaluate:
{response}

Rate the ANSWER RELEVANCE from 0.0 (completely irrelevant/off-topic) to 1.0 (highly relevant/perfectly answers the query).
Provide only the numeric score (e.g., 0.95 or 0.4) as the output. Do not include any reasoning or explanation.

Score:"""
    try:
        if provider == "gemini":
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(settings.GEMINI_LLM_MODEL)
            res = model.generate_content(prompt)
            return parse_score(res.text)
        elif provider == "openai":
            client = OpenAI(api_key=api_key)
            res = client.chat.completions.create(
                model=settings.OPENAI_LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0
            )
            return parse_score(res.choices[0].message.content)
    except Exception as e:
        print(f"Relevance judge failed: {e}")
    return 0.8  # fallback default

def evaluate_and_update_trace(
    query: str,
    response: str,
    context_text: str,
    trace_id: int,
    provider: str,
    api_key: str,
    db_url: str
):
    """
    Runs in the background after the response finishes, calculates evaluation metrics,
    and updates the Trace record in SQLite.
    We pass db_url and create a local engine because SQLite sessions cannot easily span across background threads.
    """
    # Create a fresh database connection for the background thread
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # 1. Run LLM-as-a-judge evaluations
        faithfulness = judge_faithfulness(query, response, context_text, provider, api_key)
        relevance = judge_relevance(query, response, provider, api_key)
        
        # 2. Update Trace database row
        trace = db.query(Trace).filter(Trace.id == trace_id).first()
        if trace:
            trace.faithfulness_score = faithfulness
            trace.relevance_score = relevance
            db.commit()
            print(f"Trace {trace_id} evaluated successfully: Faithfulness={faithfulness}, Relevance={relevance}")
    except Exception as e:
        print(f"Error in evaluate_and_update_trace background job: {e}")
    finally:
        db.close()
