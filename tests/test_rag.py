import pytest
from app.services.rag import reciprocal_rank_fusion

def test_rrf_ordering():
    # Setup mock chunks
    chunk_a = {"id": 1, "content": "Chunk A content", "page_number": 1, "filename": "doc.pdf", "document_id": 1}
    chunk_b = {"id": 2, "content": "Chunk B content", "page_number": 2, "filename": "doc.pdf", "document_id": 1}
    chunk_c = {"id": 3, "content": "Chunk C content", "page_number": 3, "filename": "doc.pdf", "document_id": 1}
    
    # Chunk A is first in vector, third in keyword
    # Chunk B is second in vector, first in keyword
    # Chunk C is third in vector, second in keyword
    
    vector_results = [chunk_a, chunk_b, chunk_c]
    keyword_results = [chunk_b, chunk_c, chunk_a]
    
    # Run RRF
    fused = reciprocal_rank_fusion(vector_results, keyword_results, k=60, top_n=3)
    
    assert len(fused) == 3
    # Chunk B should rank first because it is highly ranked in both (2nd and 1st)
    # RRF(B) = 1/(60+2) + 1/(60+1) = 1/62 + 1/61 = 0.0161 + 0.0163 = 0.0324
    # RRF(A) = 1/(60+1) + 1/(60+3) = 1/61 + 1/63 = 0.0163 + 0.0158 = 0.0321
    # RRF(C) = 1/(60+3) + 1/(60+2) = 1/63 + 1/62 = 0.0158 + 0.0161 = 0.0319
    # Fused order should be: Chunk B, Chunk A, Chunk C
    assert fused[0]["id"] == 2
    assert fused[1]["id"] == 1
    assert fused[2]["id"] == 3

def test_rrf_limit():
    chunk_a = {"id": 1, "content": "Chunk A", "page_number": 1, "filename": "doc.pdf", "document_id": 1}
    chunk_b = {"id": 2, "content": "Chunk B", "page_number": 2, "filename": "doc.pdf", "document_id": 1}
    
    vector_results = [chunk_a, chunk_b]
    keyword_results = [chunk_b, chunk_a]
    
    # Request only 1 top fused item
    fused = reciprocal_rank_fusion(vector_results, keyword_results, k=60, top_n=1)
    assert len(fused) == 1
