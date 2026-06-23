import pytest
from app.services.ingest import RecursiveCharacterTextSplitter

def test_recursive_splitter_simple():
    text = "Hello world! This is a simple test text to verify the custom splitter is functioning."
    # Use small chunk size to force multiple splits
    splitter = RecursiveCharacterTextSplitter(chunk_size=20, chunk_overlap=5)
    chunks = splitter.split_text(text)
    
    assert len(chunks) > 1
    # Check that each chunk is below or near the size limits (with overlap it might be slightly larger, but controlled)
    for c in chunks:
        assert len(c) <= 26  # chunk_size (20) + overlap padding (~5)

def test_recursive_splitter_separators():
    text = "Paragraph one.\n\nParagraph two with some more words.\n\nParagraph three."
    splitter = RecursiveCharacterTextSplitter(chunk_size=35, chunk_overlap=0)
    chunks = splitter.split_text(text)
    
    assert len(chunks) >= 3
    # First chunk should contain Paragraph one
    assert "Paragraph one." in chunks[0]
    assert "Paragraph three." in chunks[-1]

def test_overlap_addition():
    text = "First block. Second block. Third block."
    splitter = RecursiveCharacterTextSplitter(chunk_size=15, chunk_overlap=5)
    chunks = splitter.split_text(text)
    
    assert len(chunks) > 1
    # Subsequent chunks should contain overlap from the previous
    # Check that second chunk shares characters with the first
    first = chunks[0]
    second = chunks[1]
    overlap_segment = first[-5:]
    assert overlap_segment in second
