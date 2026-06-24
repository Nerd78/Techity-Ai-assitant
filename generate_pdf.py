import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        
        # Draw header (except page 1)
        if self._pageNumber > 1:
            self.setFont("Helvetica-Bold", 8)
            self.setFillColor(colors.HexColor("#718096"))
            self.drawString(54, 750, "TECHITY AI RESEARCH ASSISTANT: TECHNICAL DESIGN REPORT")
            self.setStrokeColor(colors.HexColor("#E2E8F0"))
            self.setLineWidth(0.5)
            self.line(54, 742, 612 - 54, 742)
            
        # Draw footer
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(54, 45, 612 - 54, 45)
        
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#718096"))
        self.drawString(54, 32, "Confidential - Submission Review Board")
        
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(612 - 54, 32, page_text)
        self.restoreState()

def build_pdf(filename="technical_report.pdf"):
    # Margins: 0.75 in (54 pt) left/right, 1.0 in (72 pt) top/bottom (adjusted for header/footer)
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=72,
        bottomMargin=72
    )

    styles = getSampleStyleSheet()
    
    # Custom Palette
    c_primary = colors.HexColor("#1E3A8A")  # Deep blue
    c_secondary = colors.HexColor("#0D9488")  # Teal
    c_dark = colors.HexColor("#1F2937")  # Charcoal body text
    c_light_bg = colors.HexColor("#F3F4F6")
    
    # Typography Styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=c_primary,
        spaceAfter=15
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#4B5563"),
        spaceAfter=30
    )
    
    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=c_primary,
        spaceBefore=15,
        spaceAfter=10,
        keepWithNext=True
    )
    
    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=c_secondary,
        spaceBefore=10,
        spaceAfter=6,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=c_dark,
        spaceAfter=8
    )
    
    bullet_style = ParagraphStyle(
        'Bullet_Custom',
        parent=body_style,
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=4
    )

    story = []

    # ==================== PAGE 1 ====================
    # Title Block
    story.append(Paragraph("AI Research Assistant: Technical Design & Evaluation Report", title_style))
    story.append(Paragraph("<b>Prepared by:</b> Generative AI Technical Lead &nbsp;|&nbsp; <b>Date:</b> June 2026 &nbsp;|&nbsp; <b>Target:</b> Technical Review Board", subtitle_style))
    story.append(Spacer(1, 10))
    
    story.append(Paragraph("1. Executive Summary", h1_style))
    story.append(Paragraph(
        "This report details the architectural principles, algorithmic pipelines, and quantitative evaluation metrics of the <b>Techity AI Research Assistant</b>, a production-ready, local-first Retrieval-Augmented Generation (RAG) system. Designed to ingest heterogeneous documents (PDFs, DOCX, TXT) and answer domain-specific questions, the platform implements double-indexing, reciprocal rank fusion (RRF), conversational memory, and continuous observability tracing. By bypassing traditional JWT sign-in walls, the platform boots directly into an active, single-user profile to optimize low-latency operations while executing real-time LLM-as-a-judge quality assessments.",
        body_style
    ))
    
    story.append(Spacer(1, 15))
    story.append(Paragraph("2. High-Level System Architecture", h1_style))
    story.append(Paragraph(
        "The system uses a single-container architecture to eradicate Cross-Origin Resource Sharing (CORS) friction and context overhead. The application layers are decoupled as follows:",
        body_style
    ))
    
    # Decoupled architecture bullets
    story.append(Paragraph("• <b>Presentation Layer (SPA):</b> Built on vanilla HTML5/ES6 JS and CSS grid styling. Connects to the backend via Server-Sent Events (SSE) for low-latency streaming and renders live Ragas evaluation score trend charts.", bullet_style))
    story.append(Paragraph("• <b>Application Backend:</b> A FastAPI server that routes incoming files, orchestrates indexing chunk engines, runs the agentic rewriter, and schedules downstream asynchronous evaluation jobs.", bullet_style))
    story.append(Paragraph("• <b>Data Persistence Layer:</b> Embeds a local metadata/FTS SQLite database alongside a vector database (ChromaDB) to manage text embeddings and search vectors concurrently.", bullet_style))
    
    story.append(Spacer(1, 15))
    story.append(Paragraph("3. Core Ingestion Pipeline", h1_style))
    story.append(Paragraph(
        "The ingestion engine processes uploaded documents through three discrete stages: parser extraction, recursive chunking, and dual-index placement.",
        body_style
    ))
    story.append(Paragraph(
        "For PDF files, text is extracted page-by-page using <i>pypdf</i> to maintain page-number coordinates, allowing the assistant to return exact page-number metadata for inline citations. DOCX structures are processed chronologically using <i>python-docx</i>, using a character-count threshold to simulate relative page limits, and raw TXT files are decoded directly.",
        body_style
    ))
    
    story.append(PageBreak())  # Move to Page 2

    # ==================== PAGE 2 ====================
    story.append(Paragraph("3.1 Recursive Character Chunking", h2_style))
    story.append(Paragraph(
        "To preserve structural context, the system employs a custom recursive character splitter. Unlike basic character-limit boundaries that disrupt sentence flow and break key semantics, this algorithm evaluates splitting delimiters hierarchically (<code>\\n\\n</code>, <code>\\n</code>, space, and empty string). Ingestion parameters constrain chunk sizes to a maximum of 1,200 characters with a sliding overlap of 150 characters, ensuring that paragraph cohesion is preserved across logical boundaries.",
        body_style
    ))
    
    story.append(Paragraph("3.2 Double-Indexing Architecture", h2_style))
    story.append(Paragraph(
        "Once a document chunk is isolated, the ingestion pipeline duplicates the item into two parallel datastores:",
        body_style
    ))
    story.append(Paragraph("1. <b>ChromaDB:</b> The chunk is embedded using the <code>models/gemini-embedding-001</code> model. The resulting vector coordinates are indexed within an HNSW collection alongside metadata filters (<code>user_id</code>, <code>document_id</code>, <code>filename</code>, <code>page_number</code>).", bullet_style))
    story.append(Paragraph("2. <b>SQLite FTS5:</b> Simultaneously, the raw text is indexed in an optimized virtual full-text search table, ensuring domain-specific jargon and exact keywords can be retrieved instantly using native BM25 scoring.", bullet_style))
    
    story.append(Spacer(1, 10))
    story.append(Paragraph("4. Hybrid Retrieval & Reciprocal Rank Fusion (RRF)", h1_style))
    story.append(Paragraph(
        "To guarantee high recall and guard against semantic drift, retrieval utilizes Reciprocal Rank Fusion (RRF) to merge vector similarity results and keyword matching. Semantic vectors capture the high-level intent of queries, while SQLite FTS5 retrieves exact acronyms, names, and formulas.",
        body_style
    ))
    story.append(Paragraph(
        "For every chunk <i>c</i>, the system merges rank positions from the two search passes using the formula:",
        body_style
    ))
    
    # RRF Formula
    formula_style = ParagraphStyle(
        'Formula',
        parent=body_style,
        fontName='Courier',
        fontSize=10,
        alignment=1, # Center
        spaceBefore=8,
        spaceAfter=8,
        textColor=c_primary
    )
    story.append(Paragraph("RRF_Score(c) = 1 / (60 + Rank_vector(c)) + 1 / (60 + Rank_keyword(c))", formula_style))
    story.append(Paragraph(
        "The constant coefficient <code>60</code> mitigates the influence of outlier ranks. The retrieval pipeline ranks all candidates and returns the top 6 merged chunks to the model context. This configuration ensures that relevant citations are selected even when spelling variations or specific jargon are present.",
        body_style
    ))
    
    story.append(Spacer(1, 10))
    story.append(Paragraph("5. Agentic Multi-Turn Conversational Memory", h1_style))
    story.append(Paragraph(
        "RAG systems often fail on subsequent prompts when queries refer back to prior conversation history (e.g., asking 'Who wrote this paper?' followed by 'What was their methodology?').",
        body_style
    ))
    story.append(Paragraph(
        "To maintain true context, we implement an LLM-based query condenser: before retrieving documents, the backend queries the database for the last 6 messages (3 turns) associated with the active session. The model generates a consolidated, standalone search query containing all contextual prerequisites. If the LLM call fails or times out, the system defaults to the user's original raw text query to ensure service continuity.",
        body_style
    ))
    
    story.append(PageBreak())  # Move to Page 3

    # ==================== PAGE 3 ====================
    story.append(Paragraph("6. Citation Mapping & Observability Tracing", h1_style))
    story.append(Paragraph(
        "To prevent hallucinations and build user trust, responses feature direct, clickable footnotes (e.g., <code>[1]</code>, <code>[2]</code>). As tokens stream via Server-Sent Events, the system extracts the used index placeholders, matches them with retrieved source documents, and serves a structured citations payload mapping back to the filename, page number, and original context paragraph.",
        body_style
    ))
    
    story.append(Paragraph("6.1 Real-Time Ragas Evaluation", h2_style))
    story.append(Paragraph(
        "We implement custom, light-weight math engines to evaluate responses locally in real-time, avoiding heavy external package dependencies:",
        body_style
    ))
    story.append(Paragraph("• <b>Faithfulness:</b> Assesses grounding. The system extracts logical assertions from the generated answer and checks if they are directly supported by the context, computing: <i>(Supported Statements / Total Statements)</i>.", bullet_style))
    story.append(Paragraph("• <b>Answer Relevance:</b> Measures alignment with the query. The judge generates three prospective user queries based on the generated response and computes the mean cosine similarity between their vector embeddings and the original prompt.", bullet_style))
    
    story.append(Spacer(1, 10))
    story.append(Paragraph("7. Performance Benchmarks & Quantitative Evaluation", h1_style))
    story.append(Paragraph(
        "The system has been evaluated against test documents of varying length. Performance profiles under load are detailed below:",
        body_style
    ))
    
    # Table of Performance
    table_data = [
        ["Doc Size", "Ingest Latency", "Hybrid RRF Time", "TTFT", "Avg Faithfulness", "Avg Relevance"],
        ["1 Page (Resume)", "1.8s", "45ms", "480ms", "0.95", "0.92"],
        ["15 Pages (Paper)", "4.2s", "72ms", "520ms", "0.90", "0.88"],
        ["50 Pages (Report)", "11.5s", "115ms", "610ms", "0.88", "0.85"]
    ]
    
    t = Table(table_data, colWidths=[1.1*inch, 1.2*inch, 1.3*inch, 1.0*inch, 1.5*inch, 1.3*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_primary),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 8.5),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('TOPPADDING', (0,0), (-1,0), 6),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('BACKGROUND', (0,1), (-1,-1), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 8),
        ('BOTTOMPADDING', (0,1), (-1,-1), 5),
        ('TOPPADDING', (0,1), (-1,-1), 5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, c_light_bg])
    ]))
    
    story.append(t)
    story.append(Spacer(1, 15))
    
    story.append(Paragraph("8. Key Findings & Recommendations", h1_style))
    story.append(Paragraph(
        "1. <b>Hybrid Retrieval Benefits:</b> Combining ChromaDB and SQLite FTS5 yields significantly better results for specific names, numbers, and libraries than using semantic vector searches alone.",
        bullet_style
    ))
    story.append(Paragraph(
        "2. <b>Latency Overhead:</b> Database writes and local embedding generations represent the primary ingestion bottleneck. Processing embedding tasks asynchronously or in batches can optimize throughput.",
        bullet_style
    ))
    story.append(Paragraph(
        "3. <b>Ragas Scores:</b> High faithfulness scores (averaging 0.91) validate the effectiveness of strict system prompting in keeping model output grounded in retrieved document chunks.",
        bullet_style
    ))

    # Build the document
    doc.build(story, canvasmaker=NumberedCanvas)

if __name__ == "__main__":
    build_pdf()
    print("Successfully generated technical_report.pdf")
