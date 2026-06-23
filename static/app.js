// ================= STATE & CONSTANTS =================
let state = {
    token: "default_token",
    username: "Researcher",
    sessions: [],
    currentSessionId: null,
    documents: [],
    traces: [],
    isSignup: false,
    provider: "gemini"
};

// API Endpoint prefix
const API_BASE = ""; 

// Charts holders
let latencyChart = null;
let evalChart = null;

// ================= DOM ELEMENTS =================
const appScreen = document.getElementById("app-screen");
const userDisplayName = document.getElementById("user-display-name");
const btnNewChat = document.getElementById("btn-new-chat");
const sessionsList = document.getElementById("sessions-list");

// Chat area
const currentChatTitle = document.getElementById("current-chat-title");
const activeDocBadge = document.getElementById("active-doc-badge");
const chatMessagesContainer = document.getElementById("chat-messages-container");
const chatInputForm = document.getElementById("chat-input-form");
const chatInput = document.getElementById("chat-input");
const btnSend = document.getElementById("btn-send");
const chatStatus = document.getElementById("chat-status");
const btnToggleRightPanel = document.getElementById("btn-toggle-right-panel");
const rightPanel = document.getElementById("right-panel");

// Right Panel tabs
const tabDocs = document.getElementById("tab-docs");
const tabAnalytics = document.getElementById("tab-analytics");
const panelDocs = document.getElementById("panel-docs");
const panelAnalytics = document.getElementById("panel-analytics");

// Files & Upload
const dropZone = document.getElementById("drop-zone");
const fileInput = document.getElementById("file-input");
const documentsList = document.getElementById("documents-list");

// Observability metrics
const metricAvgLatency = document.getElementById("metric-avg-latency");
const metricAvgFaith = document.getElementById("metric-avg-faith");
const metricAvgRelevance = document.getElementById("metric-avg-relevance");
const tracesList = document.getElementById("traces-list");

// ================= INITIALIZATION & AUTH =================
document.addEventListener("DOMContentLoaded", () => {
    // Set static user title
    if (userDisplayName) {
        userDisplayName.textContent = state.username;
    }
    
    // Load app data directly
    loadSessions();
    loadDocuments();
    loadTraces();
    
    // Setup event handlers
    setupEventHandlers();
    
    // Lucide icons replacement
    lucide.createIcons();
});

function setupEventHandlers() {

    // API Configuration managed by server environment

    // Sessions & chat
    btnNewChat.addEventListener("click", createNewChatSession);
    
    // Resize input text area dynamically
    chatInput.addEventListener("input", () => {
        chatInput.style.height = "auto";
        chatInput.style.height = (chatInput.scrollHeight) + "px";
    });

    chatInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            chatInputForm.requestSubmit();
        }
    });

    chatInputForm.onsubmit = submitQuery;

    // Toggle right panel
    btnToggleRightPanel.addEventListener("click", () => {
        rightPanel.classList.toggle("collapsed");
    });

    // Tab buttons
    tabDocs.addEventListener("click", () => {
        tabDocs.classList.add("active");
        tabAnalytics.classList.remove("active");
        panelDocs.classList.add("active");
        panelAnalytics.classList.remove("active");
    });

    tabAnalytics.addEventListener("click", () => {
        tabAnalytics.classList.add("active");
        tabDocs.classList.remove("active");
        panelAnalytics.classList.add("active");
        panelDocs.classList.remove("active");
        loadTraces(); // Refresh charts & logs
    });

    // Drag and Drop uploads
    dropZone.addEventListener("click", () => fileInput.click());
    
    dropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropZone.classList.add("dragover");
    });

    dropZone.addEventListener("dragleave", () => {
        dropZone.classList.remove("dragover");
    });

    dropZone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropZone.classList.remove("dragover");
        if (e.dataTransfer.files.length > 0) {
            uploadFiles(e.dataTransfer.files);
        }
    });

    fileInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) {
            uploadFiles(e.target.files);
        }
    });
}

// ================= SESSION LOGIC =================

async function loadSessions() {
    try {
        const res = await fetch("/v1/sessions", {
            headers: { "Authorization": `Bearer ${state.token}` }
        });
        if (!res.ok) throw new Error("Failed to load sessions");
        
        state.sessions = await res.json();
        renderSessionsList();
    } catch (err) {
        console.error(err);
    }
}

function renderSessionsList() {
    sessionsList.innerHTML = "";
    if (state.sessions.length === 0) {
        sessionsList.innerHTML = '<div class="sessions-empty">No conversations yet</div>';
        return;
    }
    
    state.sessions.forEach(session => {
        const div = document.createElement("div");
        div.className = `session-item ${session.id === state.currentSessionId ? "active" : ""}`;
        div.onclick = () => selectSession(session.id);
        
        div.innerHTML = `
            <div class="session-title-wrapper">
                <i data-lucide="message-square"></i>
                <span title="${session.title}">${session.title}</span>
            </div>
            <button class="btn-delete-session" onclick="event.stopPropagation(); deleteSession('${session.id}')">
                <i data-lucide="trash-2"></i>
            </button>
        `;
        sessionsList.appendChild(div);
    });
    lucide.createIcons();
}

async function createNewChatSession() {
    const title = prompt("Enter conversation title:", "New Research Session");
    if (!title || !title.trim()) return;
    
    try {
        const formData = new FormData();
        formData.append("title", title.trim());
        
        const res = await fetch("/v1/sessions", {
            method: "POST",
            headers: { "Authorization": `Bearer ${state.token}` },
            body: formData
        });
        
        if (!res.ok) throw new Error("Failed to create session");
        
        const newSession = await res.json();
        state.sessions.unshift(newSession);
        renderSessionsList();
        selectSession(newSession.id);
    } catch (err) {
        alert(err.message);
    }
}

async function selectSession(sessionId) {
    state.currentSessionId = sessionId;
    renderSessionsList();
    
    const activeSession = state.sessions.find(s => s.id === sessionId);
    currentChatTitle.textContent = activeSession ? activeSession.title : "Research Session";
    
    // Clear welcome message and load chat history
    chatMessagesContainer.innerHTML = '<div class="typing-indicator" id="history-loader"><span></span><span></span><span></span></div>';
    
    try {
        const res = await fetch(`/v1/sessions/${sessionId}`, {
            headers: { "Authorization": `Bearer ${state.token}` }
        });
        if (!res.ok) throw new Error("Failed to load chat history");
        
        const history = await res.json();
        chatMessagesContainer.innerHTML = "";
        
        if (history.length === 0) {
            chatMessagesContainer.innerHTML = `
                <div class="chat-welcome-card">
                    <i data-lucide="message-square-text"></i>
                    <h2>${activeSession.title}</h2>
                    <p>Start querying your documents in this session. Your conversation history is active and will guide the context-aware query rewriter.</p>
                </div>
            `;
            lucide.createIcons();
            return;
        }
        
        history.forEach(msg => {
            appendMessageBubble(msg.role, msg.content, msg.citations);
        });
        
        // Auto scroll to bottom
        chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
    } catch (err) {
        chatMessagesContainer.innerHTML = `<div class="sessions-empty" style="color:var(--danger)">Error: ${err.message}</div>`;
    }
}

async function deleteSession(sessionId) {
    if (!confirm("Are you sure you want to delete this conversation?")) return;
    
    try {
        const res = await fetch(`/v1/sessions/${sessionId}`, {
            method: "DELETE",
            headers: { "Authorization": `Bearer ${state.token}` }
        });
        if (!res.ok) throw new Error("Failed to delete session");
        
        state.sessions = state.sessions.filter(s => s.id !== sessionId);
        renderSessionsList();
        
        if (state.currentSessionId === sessionId) {
            state.currentSessionId = null;
            currentChatTitle.textContent = "Select or start a conversation";
            chatMessagesContainer.innerHTML = `
                <div class="chat-welcome-card">
                    <i data-lucide="message-square-text"></i>
                    <h2>Welcome to AI Research Assistant</h2>
                    <p>Upload your research documents, textbooks, or notes, and start extracting answers with deep inline citations, semantic mapping, and latency dashboard monitoring.</p>
                </div>
            `;
            lucide.createIcons();
        }
    } catch (err) {
        alert(err.message);
    }
}

// ================= RAG QUERY EXECUTION (SSE STREAM) =================

async function submitQuery(e) {
    e.preventDefault();
    if (!state.currentSessionId) {
        alert("Please select or create a conversation first.");
        return;
    }

    
    const queryText = chatInput.value.trim();
    if (!queryText) return;
    
    // Clear input box
    chatInput.value = "";
    chatInput.style.height = "auto";
    
    // Render user message bubble
    appendMessageBubble("user", queryText);
    chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
    
    // Create assistant bubble container with typing indicator
    const assistantBubbleId = "assistant-bubble-" + Date.now();
    const assistantRow = document.createElement("div");
    assistantRow.className = "message-row assistant-row";
    
    const bubble = document.createElement("div");
    bubble.className = "message-bubble";
    bubble.id = assistantBubbleId;
    bubble.innerHTML = `
        <div class="typing-indicator">
            <span></span>
            <span></span>
            <span></span>
        </div>
    `;
    
    assistantRow.appendChild(bubble);
    chatMessagesContainer.appendChild(assistantRow);
    chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
    
    // Prepare API fetch stream
    try {
        const formData = new FormData();
        formData.append("session_id", state.currentSessionId);
        formData.append("query", queryText);
        formData.append("provider", state.provider);
        formData.append("api_key", state.apiKey);
        
        chatStatus.textContent = "AI is thinking...";
        
        const response = await fetch("/v1/query", {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${state.token}`
            },
            body: formData
        });
        
        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.detail || "Failed to submit query");
        }
        
        // Read SSE reader stream
        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";
        let fullText = "";
        
        // Remove typing indicator on first token
        bubble.innerHTML = "";
        
        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            
            // Keep the last partial line in the buffer
            buffer = lines.pop();
            
            for (const line of lines) {
                if (line.startsWith("data: ")) {
                    const data = JSON.parse(line.substring(6));
                    
                    if (data.type === "token") {
                        fullText += data.text;
                        bubble.innerHTML = formatMarkdown(fullText);
                        chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
                    } else if (data.type === "citations") {
                        // Render citation expansion card below text
                        renderCitations(bubble, data.citations);
                        chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
                    } else if (data.type === "error") {
                        bubble.innerHTML = `<span style="color:var(--danger)">Error: ${data.text}</span>`;
                    }
                }
            }
        }
        chatStatus.textContent = "Response complete.";
        setTimeout(() => chatStatus.textContent = "", 3000);
        
    } catch (err) {
        bubble.innerHTML = `<span style="color:var(--danger)">Error: ${err.message}</span>`;
        chatStatus.textContent = "Error occurred.";
    }
}

function appendMessageBubble(role, content, citations = []) {
    const row = document.createElement("div");
    row.className = `message-row ${role}-row`;
    
    const bubble = document.createElement("div");
    bubble.className = "message-bubble";
    bubble.innerHTML = formatMarkdown(content);
    
    if (role === "assistant" && citations && citations.length > 0) {
        renderCitations(bubble, citations);
    }
    
    row.appendChild(bubble);
    chatMessagesContainer.appendChild(row);
}

function renderCitations(bubbleElement, citations) {
    if (!citations || citations.length === 0) return;
    
    const citationsBox = document.createElement("div");
    citationsBox.className = "citations-box";
    
    const citationsHeader = document.createElement("div");
    citationsHeader.className = "citations-header";
    citationsHeader.innerHTML = `
        <i data-lucide="chevron-right"></i>
        <span>References (${citations.length})</span>
    `;
    
    const itemsList = document.createElement("div");
    itemsList.className = "citations-list-items hidden";
    
    citations.forEach(c => {
        const item = document.createElement("div");
        item.className = "citation-card";
        item.innerHTML = `
            <div class="citation-source">
                <i data-lucide="file-text"></i>
                <span>[${c.ref_index}] ${c.filename} - Page ${c.page_number}</span>
            </div>
            <div class="citation-excerpt">"${c.excerpt}"</div>
        `;
        itemsList.appendChild(item);
    });
    
    citationsHeader.onclick = () => {
        citationsHeader.classList.toggle("open");
        itemsList.classList.toggle("hidden");
        // Update Chevron icon
        const icon = citationsHeader.querySelector("i");
        if (citationsHeader.classList.contains("open")) {
            icon.style.transform = "rotate(90deg)";
        } else {
            icon.style.transform = "rotate(0deg)";
        }
    };
    
    citationsBox.appendChild(citationsHeader);
    citationsBox.appendChild(itemsList);
    bubbleElement.appendChild(citationsBox);
    lucide.createIcons();
}

function formatMarkdown(text) {
    // Escape HTML to prevent injection
    let clean = text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
        
    // Format bold text **bold**
    clean = clean.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
    
    // Format code block `code`
    clean = clean.replace(/`(.*?)`/g, "<code>$1</code>");
    
    // Format linebreaks
    clean = clean.replace(/\n/g, "<br>");
    
    return clean;
}

// ================= DOCUMENT MANAGEMENT =================

async function loadDocuments() {
    try {
        const res = await fetch("/v1/documents", {
            headers: { "Authorization": `Bearer ${state.token}` }
        });
        if (!res.ok) throw new Error("Failed to load documents");
        
        state.documents = await res.json();
        renderDocumentsList();
        
        // Update badge
        if (state.documents.length > 0) {
            activeDocBadge.classList.remove("hidden");
            activeDocBadge.textContent = `${state.documents.length} doc${state.documents.length > 1 ? 's' : ''} active`;
        } else {
            activeDocBadge.classList.add("hidden");
        }
    } catch (err) {
        console.error(err);
    }
}

function renderDocumentsList() {
    documentsList.innerHTML = "";
    if (state.documents.length === 0) {
        documentsList.innerHTML = '<div class="docs-empty">No documents uploaded yet</div>';
        return;
    }
    
    state.documents.forEach(doc => {
        const sizeKB = (doc.size_bytes / 1024).toFixed(1);
        const div = document.createElement("div");
        div.className = "doc-item";
        div.innerHTML = `
            <div class="doc-info">
                <i data-lucide="file-text"></i>
                <div class="doc-meta">
                    <span class="doc-name" title="${doc.filename}">${doc.filename}</span>
                    <span class="doc-size">${doc.file_type.toUpperCase()} • ${sizeKB} KB</span>
                </div>
            </div>
            <button class="btn-delete-doc" onclick="deleteDocument(${doc.id})">
                <i data-lucide="trash-2"></i>
            </button>
        `;
        documentsList.appendChild(div);
    });
    lucide.createIcons();
}

async function uploadFiles(files) {
    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        
        // Add fake item in lists to show loading state
        const loadingDiv = document.createElement("div");
        loadingDiv.className = "doc-item";
        loadingDiv.id = `doc-loading-${i}`;
        loadingDiv.innerHTML = `
            <div class="doc-info">
                <div class="typing-indicator" style="height:auto"><span></span><span></span><span></span></div>
                <div class="doc-meta" style="margin-left:10px">
                    <span class="doc-name">${file.name}</span>
                    <span class="doc-size">Processing and chunking...</span>
                </div>
            </div>
        `;
        documentsList.prepend(loadingDiv);
        
        const formData = new FormData();
        formData.append("file", file);
        formData.append("provider", state.provider);
        formData.append("api_key", state.apiKey);
        
        try {
            const res = await fetch("/v1/ingest", {
                method: "POST",
                headers: { "Authorization": `Bearer ${state.token}` },
                body: formData
            });
            
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || "Ingest failed");
            
            // Remove loading representation and reload
            loadingDiv.remove();
            loadDocuments();
        } catch (err) {
            loadingDiv.innerHTML = `
                <div class="doc-info" style="color:var(--danger)">
                    <i data-lucide="alert-circle" style="color:var(--danger)"></i>
                    <div class="doc-meta">
                        <span class="doc-name">${file.name}</span>
                        <span class="doc-size">Error: ${err.message}</span>
                    </div>
                </div>
            `;
            lucide.createIcons();
            // Automatically clean error block in 6 seconds
            setTimeout(() => loadingDiv.remove(), 6000);
        }
    }
}

async function deleteDocument(docId) {
    if (!confirm("Are you sure you want to delete this document?")) return;
    
    try {
        const res = await fetch(`/v1/documents/${docId}`, {
            method: "DELETE",
            headers: { "Authorization": `Bearer ${state.token}` }
        });
        if (!res.ok) throw new Error("Failed to delete document");
        
        loadDocuments();
    } catch (err) {
        alert(err.message);
    }
}

// ================= ANALYTICS & OBSERVABILITY =================

async function loadTraces() {
    try {
        const res = await fetch("/v1/traces", {
            headers: { "Authorization": `Bearer ${state.token}` }
        });
        if (!res.ok) throw new Error("Failed to load traces");
        
        state.traces = await res.json();
        renderTracesDashboard();
    } catch (err) {
        console.error(err);
    }
}

function renderTracesDashboard() {
    // 1. Calculate Averages
    if (state.traces.length === 0) {
        metricAvgLatency.textContent = "0ms";
        metricAvgFaith.textContent = "0.0";
        metricAvgRelevance.textContent = "0.0";
        tracesList.innerHTML = '<div class="traces-empty">No query traces logged yet</div>';
        destroyCharts();
        return;
    }
    
    let sumLatency = 0;
    let sumFaith = 0;
    let faithCount = 0;
    let sumRel = 0;
    let relCount = 0;
    
    state.traces.forEach(t => {
        sumLatency += t.latency_ms || 0;
        if (t.faithfulness_score !== null) {
            sumFaith += t.faithfulness_score;
            faithCount++;
        }
        if (t.relevance_score !== null) {
            sumRel += t.relevance_score;
            relCount++;
        }
    });
    
    const avgLatency = Math.round(sumLatency / state.traces.length);
    const avgFaith = faithCount > 0 ? (sumFaith / faithCount).toFixed(2) : "N/A";
    const avgRelevance = relCount > 0 ? (sumRel / relCount).toFixed(2) : "N/A";
    
    metricAvgLatency.textContent = `${avgLatency}ms`;
    metricAvgFaith.textContent = avgFaith;
    metricAvgRelevance.textContent = avgRelevance;
    
    // 2. Render List of Traces
    tracesList.innerHTML = "";
    state.traces.forEach(t => {
        const dateStr = new Date(t.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        const hasScore = t.faithfulness_score !== null;
        
        const row = document.createElement("div");
        row.className = "trace-row";
        row.innerHTML = `
            <div class="trace-top">
                <span class="trace-time">${dateStr}</span>
                <span class="trace-tokens">${t.total_tokens || 0} tokens</span>
            </div>
            <div class="trace-query" title="${t.query}">${t.query}</div>
            <div class="trace-meta-tags">
                <span class="tag-latency">${Math.round(t.latency_ms)}ms</span>
                <span class="tag-score ${hasScore ? '' : 'null'}">
                    Faithfulness: ${hasScore ? t.faithfulness_score.toFixed(1) : 'Pending'}
                </span>
            </div>
            <div class="trace-detail-expanded hidden" id="trace-detail-${t.id}">
                <div><strong>Condensed Search Query:</strong> ${t.condensed_query || "N/A"}</div>
                <div><strong>Assistant Reply Excerpt:</strong> ${t.response}</div>
            </div>
        `;
        row.onclick = () => {
            const detail = row.querySelector(`.trace-detail-expanded`);
            detail.classList.toggle("hidden");
        };
        
        tracesList.appendChild(row);
    });
    
    // 3. Render Chart.js
    renderCharts();
}

function renderCharts() {
    // Destroy previous charts if they exist
    destroyCharts();
    
    // Data (reverse to show chronological left-to-right order)
    const reversedTraces = [...state.traces].reverse().slice(-10); // Show last 10 queries
    const labels = reversedTraces.map((_, idx) => `Q${idx + 1}`);
    const latencies = reversedTraces.map(t => t.latency_ms);
    const tokens = reversedTraces.map(t => t.total_tokens || 0);
    const faithfulness = reversedTraces.map(t => t.faithfulness_score);
    const relevance = reversedTraces.map(t => t.relevance_score);
    
    // Latency Chart
    const ctxLat = document.getElementById("chart-latency").getContext("2d");
    latencyChart = new Chart(ctxLat, {
        type: "line",
        data: {
            labels: labels,
            datasets: [
                {
                    label: "Latency (ms)",
                    data: latencies,
                    borderColor: "#6366f1",
                    backgroundColor: "rgba(99, 102, 241, 0.1)",
                    borderWidth: 2,
                    tension: 0.3,
                    yAxisID: "y"
                },
                {
                    label: "Tokens",
                    data: tokens,
                    borderColor: "#a855f7",
                    backgroundColor: "rgba(168, 85, 247, 0.1)",
                    borderWidth: 2,
                    tension: 0.3,
                    yAxisID: "y1"
                }
            ]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    type: "linear",
                    display: true,
                    position: "left",
                    grid: { color: "#222731" },
                    ticks: { color: "#a0aec0" }
                },
                y1: {
                    type: "linear",
                    display: true,
                    position: "right",
                    grid: { drawOnChartArea: false },
                    ticks: { color: "#a0aec0" }
                },
                x: {
                    ticks: { color: "#a0aec0" }
                }
            },
            plugins: {
                legend: { labels: { color: "#f3f4f6" } }
            }
        }
    });
    
    // Evaluation Chart
    const ctxEval = document.getElementById("chart-eval").getContext("2d");
    evalChart = new Chart(ctxEval, {
        type: "bar",
        data: {
            labels: labels,
            datasets: [
                {
                    label: "Faithfulness",
                    data: faithfulness,
                    backgroundColor: "#10b981",
                    borderRadius: 4
                },
                {
                    label: "Relevance",
                    data: relevance,
                    backgroundColor: "#3b82f6",
                    borderRadius: 4
                }
            ]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    min: 0.0,
                    max: 1.0,
                    grid: { color: "#222731" },
                    ticks: { color: "#a0aec0" }
                },
                x: {
                    ticks: { color: "#a0aec0" }
                }
            },
            plugins: {
                legend: { labels: { color: "#f3f4f6" } }
            }
        }
    });
}

function destroyCharts() {
    if (latencyChart) {
        latencyChart.destroy();
        latencyChart = null;
    }
    if (evalChart) {
        evalChart.destroy();
        evalChart = null;
    }
}
