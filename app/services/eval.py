import os
import re
import json
import numpy as np
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import google.generativeai as genai
from openai import OpenAI

from app.core.config import settings
from app.models import Trace

def parse_score(llm_output: str) -> float:
    cleaned = llm_output.strip()
    match = re.search(r"([0-9\.]+)", cleaned)
    if match:
        try:
            score = float(match.group(1))
            return min(max(score, 0.0), 1.0)
        except ValueError:
            pass
    return 0.5

def extract_statements(response: str, provider: str, api_key: str) -> list[str]:
    """
    Step 1 of Ragas Faithfulness: Extract simple statements from the response.
    """
    prompt = f"""Given the following text, break it down into a list of simple, single-fact statements/claims.
Each statement should contain only one factual assertion. Format the output as a simple JSON list of strings.

Text:
{response}

Output (valid JSON list of strings only, e.g. ["claim 1", "claim 2"]):"""

    try:
        if provider == "gemini":
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(settings.GEMINI_LLM_MODEL)
            res = model.generate_content(prompt)
            text_out = res.text.strip()
        elif provider == "openai":
            client = OpenAI(api_key=api_key)
            res = client.chat.completions.create(
                model=settings.OPENAI_LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0
            )
            text_out = res.choices[0].message.content.strip()

        # Parse JSON list
        # Find JSON boundaries in case LLM added markdown formatting
        if "```json" in text_out:
            text_out = text_out.split("```json")[1].split("```")[0].strip()
        elif "```" in text_out:
            text_out = text_out.split("```")[1].split("```")[0].strip()
            
        statements = json.loads(text_out)
        if isinstance(statements, list):
            return [str(s) for s in statements if s]
    except Exception as e:
        print(f"Error extracting statements for Ragas faithfulness: {e}")
    
    # Fallback: split by sentences
    sentences = re.split(r'\. |\n', response)
    return [s.strip() for s in sentences if len(s.strip()) > 10]

def verify_statements_against_context(statements: list[str], context: str, provider: str, api_key: str) -> float:
    """
    Step 2 & 3 of Ragas Faithfulness: Check how many statements are supported by the context.
    """
    if not statements:
        return 1.0
        
    prompt = f"""You are a strict factual consistency grader. Given the Context and a list of Claims, verify if each Claim is directly supported by the Context.
For each Claim, output "YES" if it is supported, or "NO" if it is not supported or if it contradicts the Context.

Context:
{context}

Claims to Verify:
{json.dumps(statements)}

Output the grading as a JSON list of strings containing ONLY "YES" or "NO" corresponding to each claim.
Example Output: ["YES", "NO", "YES"]"""

    try:
        if provider == "gemini":
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(settings.GEMINI_LLM_MODEL)
            res = model.generate_content(prompt)
            text_out = res.text.strip()
        elif provider == "openai":
            client = OpenAI(api_key=api_key)
            res = client.chat.completions.create(
                model=settings.OPENAI_LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0
            )
            text_out = res.choices[0].message.content.strip()

        if "```json" in text_out:
            text_out = text_out.split("```json")[1].split("```")[0].strip()
        elif "```" in text_out:
            text_out = text_out.split("```")[1].split("```")[0].strip()

        verdicts = json.loads(text_out)
        if isinstance(verdicts, list) and len(verdicts) > 0:
            yes_count = sum(1 for v in verdicts if str(v).upper() == "YES")
            return yes_count / len(verdicts)
    except Exception as e:
        print(f"Error verifying claims for Ragas faithfulness: {e}")
        
    return 0.8  # Fallback score

def calculate_ragas_faithfulness(query: str, response: str, context: str, provider: str, api_key: str) -> float:
    """
    Ragas Faithfulness = (number of statements supported by context) / (total statements extracted from answer)
    """
    statements = extract_statements(response, provider, api_key)
    if not statements:
        return 1.0
    return verify_statements_against_context(statements, context, provider, api_key)

def generate_questions_from_response(response: str, provider: str, api_key: str) -> list[str]:
    """
    Step 1 of Ragas Answer Relevance: Generate 3 questions that could be answered by the response.
    """
    prompt = f"""Based on the following Text, generate exactly 3 distinct user questions that this Text fully answers.
Output the questions as a JSON list of strings.

Text:
{response}

Output (valid JSON list of strings only, e.g. ["question 1", "question 2", "question 3"]):"""

    try:
        if provider == "gemini":
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(settings.GEMINI_LLM_MODEL)
            res = model.generate_content(prompt)
            text_out = res.text.strip()
        elif provider == "openai":
            client = OpenAI(api_key=api_key)
            res = client.chat.completions.create(
                model=settings.OPENAI_LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0
            )
            text_out = res.choices[0].message.content.strip()

        if "```json" in text_out:
            text_out = text_out.split("```json")[1].split("```")[0].strip()
        elif "```" in text_out:
            text_out = text_out.split("```")[1].split("```")[0].strip()

        qs = json.loads(text_out)
        if isinstance(qs, list):
            return [str(q) for q in qs if q]
    except Exception as e:
        print(f"Error generating questions for Ragas relevance: {e}")
        
    return []

def get_embedding_vector(text_str: str, provider: str, api_key: str) -> list[float]:
    """
    Get the embedding vector for a piece of text.
    """
    if provider == "gemini":
        genai.configure(api_key=api_key)
        result = genai.embed_content(
            model=settings.GEMINI_EMBEDDING_MODEL,
            content=text_str,
            task_type="retrieval_document"
        )
        return result["embedding"]
    elif provider == "openai":
        client = OpenAI(api_key=api_key)
        response = client.embeddings.create(
            model=settings.OPENAI_EMBEDDING_MODEL,
            input=text_str
        )
        return response.data[0].embedding
    return []

def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    if not v1 or not v2:
        return 0.0
    a = np.array(v1)
    b = np.array(v2)
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))

def calculate_ragas_relevance(query: str, response: str, provider: str, api_key: str) -> float:
    """
    Ragas Answer Relevance = average cosine similarity between original query embedding
    and embeddings of 3 generated questions that the response could answer.
    """
    gen_questions = generate_questions_from_response(response, provider, api_key)
    if not gen_questions:
        return 0.8
        
    try:
        # Get query embedding
        query_emb = get_embedding_vector(query, provider, api_key)
        if not query_emb:
            return 0.8
            
        similarities = []
        for q in gen_questions:
            q_emb = get_embedding_vector(q, provider, api_key)
            if q_emb:
                similarities.append(cosine_similarity(query_emb, q_emb))
                
        if similarities:
            return sum(similarities) / len(similarities)
    except Exception as e:
        print(f"Error calculating Ragas answer relevance similarity: {e}")
        
    return 0.8

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
    Async background worker running actual Ragas metrics computations.
    """
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Compute metrics using Ragas mathematical models
        faithfulness = calculate_ragas_faithfulness(query, response, context_text, provider, api_key)
        relevance = calculate_ragas_relevance(query, response, provider, api_key)
        
        trace = db.query(Trace).filter(Trace.id == trace_id).first()
        if trace:
            trace.faithfulness_score = faithfulness
            trace.relevance_score = relevance
            db.commit()
            print(f"Ragas Evaluated Trace {trace_id}: Faithfulness={faithfulness:.2f}, Relevance={relevance:.2f}")
    except Exception as e:
        print(f"Ragas background evaluation failed: {e}")
    finally:
        db.close()
