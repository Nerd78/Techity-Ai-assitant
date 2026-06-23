# Techity AI Research Assistant

An end-to-end, production-ready AI Research Assistant that ingests research documents (PDF, DOCX, TXT), performs hybrid search (Vector Embeddings + BM25 keyword matching) with Reciprocal Rank Fusion (RRF), streams responses with precise inline citations, and calculates real-time evaluation scores (Faithfulness and Relevance) via a custom observability dashboard.

---

## 🏗️ System Architecture

```
                               +-----------------------------+
                               |    Browser / UI (SPA)       |
                               |  Vanilla HTML5/CSS3/JS    |
                               +--------------+--------------+
                                              |
                                              | HTTP / Server-Sent Events
                                              v
+---------------------------------------------+----------------------------------------------+
|                                  FastAPI Backend Service                                   |
|                                                                                            |
|   +------------------+     +------------------------+     +-----------------------------+  |
|   |  Auth Router     |     |   Ingestion Router     |     |      Query / RAG Router     |  |
|   |  • JWT Tokens    |     |   • File Parsers       |     |      • Agentic Rewriter     |  |
|   |  • BCrypt Pass   |     |   • Recursive Chunker  |     |      • Hybrid Search Engine |  |
|   +--------+---------+     +-----------+------------+     +--------------+--------------+  |
|            |                           |                                 |                 |
|            | Write                     | Vector Embed / Insert           | Read / Query    |
|            v                           v                                 v                 |
|   +--------+---------+     +-----------+------------+     +--------------+--------------+  |
|   | SQLite Database  |     |   ChromaDB (Embedded)  |     |      LLM APIs Gateway       |  |
|   | • Users / Chats  |     |   • HNSW Vector Index  |     |      • Gemini / OpenAI      |  |
|   | • FTS5 Keywords  |     |   • Meta Filters       |     |      • Judge Evaluator      |  |
|   | • Query Traces   |     |                        |     |                      |  |
|   +------------------+     +------------------------+     +-----------------------------+  |
|                                                                                            |
+--------------------------------------------------------------------------------------------+
```

---

## 🌟 Key Technical Features

### 1. Ingestion & Document Processing
* **Parsers**: Raw page-by-page text extraction for PDFs (`pypdf`), structural parsing for Word documents (`python-docx`), and utf-8 text stream decoding for TXT files.
* **Recursive Chunker**: A custom, zero-dependency `RecursiveCharacterTextSplitter` that splits documents using logical hierarchy delimiters (`\n\n`, `\n`, ` `, `""`) preserving paragraph cohesion.
* **Double-Indexing**: Chunks are processed into:
  1. High-dimensional vector embeddings stored in a persistent **ChromaDB** index.
  2. Structured records in an optimized **SQLite FTS5 (Full-Text Search)** virtual index.

### 2. Hybrid Retrieval & RRF
To ensure high retrieval recall and precision, queries execute a dual-search retrieval:
1. **Semantic Search**: Vector similarity query in ChromaDB filtered by user ownership metadata.
2. **Keyword Search**: Cleaned term-based SQLite FTS5 query ranking chunks by database BM25 weights.
3. **Reciprocal Rank Fusion (RRF)**: Merges scores from both indexes:
   $$RRF(c) = \sum_{m \in M} \frac{1}{60 + \text{rank}_m(c)}$$
   This prevents semantic drift and catches domain-specific jargon terms.

### 3. Agentic Query Rewriter
Multi-turn conversations suffer from query reference losses (e.g., "What is its revenue?" following "Analyze Apple Inc."). We implement an LLM-based query-condensation agent that rewrites conversational inputs into descriptive, standalone queries using previous messages.

### 4. Source Citation Extraction
The LLM prompt instructs references to be marked with bracketed integers corresponding to retrieved context IDs (e.g., `[1]`). At the end of the streaming response, the system isolates citation cards mapping back to source filenames and page numbers.

### 5. Local Observability & Tracing Dashboard
Includes a built-in admin dashboard detailing:
* **Latency & Token Usage Trends** via Chart.js.
* **LLM-as-a-judge Evaluation**: Real-time asynchronous jobs verify **Faithfulness** (context grounding / hallucination check) and **Answer Relevance** (satisfies initial prompt), scoring responses from `0.0` to `1.0`.

---

## 🚀 Getting Started (Dockerized Setup)

Ensure you have [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/) installed on your host machine.

### 1. Run the Application
In the project root directory, run:
```bash
docker-compose up --build
```
This builds the single container image containing the FastAPI backend service and automatically mounts static files.

### 2. Open the Interface
Access the web dashboard in your browser:
```
http://localhost:8000
```

### 3. Sign In & Setup Keys
1. Create a new user account (Sign Up) and Log In.
2. In the Left Sidebar under **API Configuration**, select your provider (**Google Gemini** or **OpenAI**) and paste your API key. (Credentials are stored locally in browser session storage).
3. Drag & drop files to compile your vector database indices.

---

## 🛠️ Local Development (Without Docker)

If you prefer to run the application locally on your machine:

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run uvicorn
```bash
uvicorn app.main:app --reload --port 8000
```

### 3. Run Unit Tests
A pytest suite is provided to validate auth, custom chunking, and RRF calculations:
```bash
pytest
```

---

## 📂 Project Directory Structure

```
├── app/                         # FastAPI Application Module
│   ├── core/
│   │   ├── config.py            # Pydantic Configuration settings
│   │   ├── database.py          # SQLAlchemy Session setup
│   │   └── security.py          # JWT Token & Password Hash utils
│   ├── models.py                # SQL models (Users, Chat, Document, Trace)
│   └── services/
│       ├── ingest.py            # File extraction, splitters, Chroma/FTS indexes
│       ├── rag.py               # Rewriter, Hybrid search, SSE Stream generator
│       └── eval.py              # LLM-as-a-judge evaluations
├── static/                      # SPA Web Assets (served by FastAPI)
│   ├── index.html               # Triple-column frontend UI layout
│   ├── styles.css               # Modern glassmorphism dark stylesheet
│   └── app.js                   # Client state machine, SSE parser, Chart.js integrations
├── tests/                       # Unit Test Suite
│   ├── test_auth.py             # Auth endpoints testing
│   ├── test_ingest.py           # Splitter constraints testing
│   └── test_rag.py              # RRF order math testing
├── Dockerfile                   # Python container configuration
├── docker-compose.yml           # Local volume persistence and ports
├── requirements.txt             # Python requirements list
└── README.md                    # Technical documentation
```
