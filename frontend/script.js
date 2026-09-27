// ==========================================
// BACKEND URL & GLOBAL STATE
// ==========================================

const API_URL = "http://127.0.0.1:8000";

let activeCategory = "All";
let aiMessageCounter = 0;

// Speech Recognition & Synthesis references
let recognition = null;
let isListening = false;
let currentUtterance = null;
let currentSpeakingMsgId = null;


// ==========================================
// PAGE NAVIGATION
// ==========================================

function showSection(sectionName) {
    const sections = document.querySelectorAll(".section");
    sections.forEach(section => {
        section.classList.remove("active");
    });

    const selected = document.getElementById(sectionName);
    if (selected) {
        selected.classList.add("active");
    }

    const titles = {
        dashboard: "Dashboard",
        documents: "Documents",
        search: "Semantic Search",
        assistant: "AI Assistant"
    };

    document.getElementById("pageTitle").textContent = titles[sectionName] || "Dashboard";

    const navItems = document.querySelectorAll(".nav-item");
    navItems.forEach(item => {
        item.classList.remove("active");
    });

    if (sectionName === "dashboard") navItems[0].classList.add("active");
    if (sectionName === "documents") navItems[1].classList.add("active");
    if (sectionName === "search") navItems[2].classList.add("active");
    if (sectionName === "assistant") navItems[3].classList.add("active");

    // Scroll to top of main
    window.scrollTo({ top: 0, behavior: "smooth" });
}


// ==========================================
// CHECK BACKEND
// ==========================================

async function checkBackend() {
    try {
        const response = await fetch(`${API_URL}/api/status`);
        if (!response.ok) {
            throw new Error("Backend unavailable");
        }
        const data = await response.json();
        document.getElementById("backendStatus").textContent = "Online (v" + (data.version || "2.0") + ")";
    } catch (error) {
        document.getElementById("backendStatus").textContent = "Offline";
        console.error("Backend health check failed:", error);
    }
}


// ==========================================
// FILE SELECTION
// ==========================================

document.getElementById("fileInput").addEventListener("change", function () {
    const file = this.files[0];
    const selectedFile = document.getElementById("selectedFile");
    if (file) {
        selectedFile.textContent = file.name;
    } else {
        selectedFile.textContent = "No file selected";
    }
});


// ==========================================
// UPLOAD DOCUMENT
// ==========================================

async function uploadDocument() {
    const fileInput = document.getElementById("fileInput");
    const message = document.getElementById("uploadMessage");

    if (!fileInput.files.length) {
        message.className = "message error";
        message.textContent = "Please select a file to upload.";
        return;
    }

    const file = fileInput.files[0];
    const allowedTypes = [".pdf", ".docx", ".txt"];
    const extension = file.name.substring(file.name.lastIndexOf(".")).toLowerCase();

    if (!allowedTypes.includes(extension)) {
        message.className = "message error";
        message.textContent = "Only PDF, DOCX and TXT files are supported.";
        return;
    }

    message.className = "message info";
    message.textContent = "Uploading, analyzing and indexing document...";

    const formData = new FormData();
    formData.append("file", file);

    try {
        const response = await fetch(`${API_URL}/api/upload`, {
            method: "POST",
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Upload failed");
        }

        message.className = "message success";
        message.textContent = `✓ ${data.message} • Category: ${data.category || 'Organized'} • (${data.chunks} chunks created)`;

        fileInput.value = "";
        document.getElementById("selectedFile").textContent = "No file selected";

        await loadDocuments();

    } catch (error) {
        console.error(error);
        message.className = "message error";
        message.textContent = "Upload failed: " + error.message;
    }
}


// ==========================================
// DOCUMENT ORGANIZATION & CATEGORY FILTER
// ==========================================

function setCategoryFilter(category) {
    activeCategory = category;

    // Update active state on category filter buttons
    const pills = document.querySelectorAll(".category-pill");
    pills.forEach(pill => {
        if (pill.textContent.trim().toLowerCase() === category.toLowerCase() ||
            (category === "All" && pill.textContent.trim().toLowerCase() === "all categories")) {
            pill.classList.add("active");
        } else {
            pill.classList.remove("active");
        }
    });

    loadDocuments();
}


async function loadDocuments() {
    const container = document.getElementById("documentList");

    try {
        let url = `${API_URL}/api/documents`;
        if (activeCategory && activeCategory !== "All") {
            url += `?category=${encodeURIComponent(activeCategory)}`;
        }

        const response = await fetch(url);
        if (!response.ok) {
            throw new Error("Could not load documents");
        }

        const documents = await response.json();

        // Update dashboard count if loaded with All
        if (activeCategory === "All") {
            document.getElementById("documentCount").textContent = documents.length;
        }

        if (documents.length === 0) {
            const filterNote = activeCategory !== "All"
                ? `No documents found in "${escapeHTML(activeCategory)}".`
                : "No documents uploaded yet.";
            container.innerHTML = `
                <div class="empty-state">
                    ${filterNote}
                </div>
            `;
            return;
        }

        container.innerHTML = documents.map(doc => {
            const category = doc.category || "Other";
            const categorySlug = category.toLowerCase().replace(/\s+/g, "-");
            const tags = Array.isArray(doc.tags) ? doc.tags : [];

            return `
                <div class="document-item">
                    <div class="document-info">
                        <div class="document-icon">
                            ${getFileIcon(doc.file_type)}
                        </div>

                        <div class="document-details">
                            <div class="document-header-row">
                                <span class="document-name">${escapeHTML(doc.filename)}</span>
                                <span class="category-badge cat-${categorySlug}">${escapeHTML(category)}</span>
                            </div>

                            <div class="document-meta">
                                <span>${doc.file_type}</span>
                                <span>•</span>
                                <span>${formatFileSize(doc.file_size)}</span>
                            </div>

                            ${tags.length > 0 ? `
                                <div class="document-tags">
                                    ${tags.map(t => `<span class="tag-chip">#${escapeHTML(t)}</span>`).join("")}
                                </div>
                            ` : ""}
                        </div>
                    </div>

                    <div class="document-actions">
                        <button
                            class="summary-btn"
                            onclick="openDocumentSummary(${doc.id})"
                            title="Generate Summary"
                        >
                            📋 Summary
                        </button>
                        <button
                            class="delete-btn"
                            onclick="deleteDocument(${doc.id})"
                            title="Delete Document"
                        >
                            Delete
                        </button>
                    </div>
                </div>
            `;
        }).join("");

    } catch (error) {
        console.error(error);
        container.innerHTML = `
            <div class="empty-state">
                Could not load documents. Please ensure the backend is running.
            </div>
        `;
    }
}


async function deleteDocument(id) {
    const confirmDelete = confirm("Are you sure you want to delete this document?");
    if (!confirmDelete) return;

    try {
        const response = await fetch(`${API_URL}/api/documents/${id}`, {
            method: "DELETE"
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || "Delete failed");
        }

        await loadDocuments();

    } catch (error) {
        alert("Delete failed: " + error.message);
    }
}


// ==========================================
// DOCUMENT SUMMARY MODAL
// ==========================================

async function openDocumentSummary(documentId) {
    const modal = document.getElementById("summaryModal");
    const modalTitle = document.getElementById("modalDocTitle");
    const modalMeta = document.getElementById("modalDocMeta");
    const statsGrid = document.getElementById("modalStatsGrid");
    const overviewP = document.getElementById("modalOverview");
    const keyPointsUl = document.getElementById("modalKeyPoints");

    modal.style.display = "flex";
    modalTitle.textContent = "Loading Document Summary...";
    modalMeta.innerHTML = "";
    statsGrid.innerHTML = "";
    overviewP.textContent = "Analyzing document content and extracting key insights...";
    keyPointsUl.innerHTML = "<li>Extracting highlights...</li>";

    try {
        const response = await fetch(`${API_URL}/api/documents/${documentId}/summary`);
        if (!response.ok) {
            throw new Error("Failed to generate summary");
        }

        const data = await response.json();

        modalTitle.textContent = data.filename;
        const categorySlug = (data.category || "other").toLowerCase().replace(/\s+/g, "-");

        modalMeta.innerHTML = `
            <span class="category-badge cat-${categorySlug}">${escapeHTML(data.category || "Other")}</span>
            ${(data.tags || []).map(t => `<span class="tag-chip">#${escapeHTML(t)}</span>`).join("")}
        `;

        statsGrid.innerHTML = `
            <div class="modal-stat-card">
                <span>File Format</span>
                <strong>${data.file_type || "N/A"}</strong>
            </div>
            <div class="modal-stat-card">
                <span>File Size</span>
                <strong>${formatFileSize(data.file_size)}</strong>
            </div>
            <div class="modal-stat-card">
                <span>Total Chunks</span>
                <strong>${data.chunks_count || 0}</strong>
            </div>
            <div class="modal-stat-card">
                <span>Reading Time</span>
                <strong>${data.reading_time || "1 min read"}</strong>
            </div>
        `;

        overviewP.textContent = data.overview || "No overview available.";

        if (data.key_points && data.key_points.length > 0) {
            keyPointsUl.innerHTML = data.key_points.map(pt => `<li>${escapeHTML(pt)}</li>`).join("");
        } else {
            keyPointsUl.innerHTML = `<li>Full content indexed and ready for semantic search.</li>`;
        }

    } catch (error) {
        console.error(error);
        modalTitle.textContent = "Error Loading Summary";
        overviewP.textContent = "Could not generate summary: " + error.message;
        keyPointsUl.innerHTML = "";
    }
}


function closeSummaryModal(event) {
    if (event && event.target && event.target !== document.getElementById("summaryModal") && !event.target.classList.contains("modal-close-btn") && !event.target.closest(".modal-footer button")) {
        return;
    }
    const modal = document.getElementById("summaryModal");
    modal.style.display = "none";
}


// ==========================================
// IMPROVED SEMANTIC SEARCH
// ==========================================

async function searchDocuments() {
    const input = document.getElementById("searchInput");
    const query = input.value.trim();
    const resultsContainer = document.getElementById("searchResults");

    if (!query) {
        resultsContainer.innerHTML = `
            <div class="empty-state">
                Please enter something to search.
            </div>
        `;
        return;
    }

    resultsContainer.innerHTML = `
        <div class="empty-state">
            <span class="searching-spinner"></span> Searching semantically...
        </div>
    `;

    try {
        const response = await fetch(`${API_URL}/api/search`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                query: query,
                limit: 5,
                threshold: 0.30
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Search failed");
        }

        if (!data.results || data.results.length === 0) {
            resultsContainer.innerHTML = `
                <div class="search-empty-box">
                    <div class="search-empty-icon">🔍</div>
                    <h4>No matching results found</h4>
                    <p>No content in your uploaded documents met the relevance threshold for "${escapeHTML(query)}".</p>
                    <small>Try using different keywords or upload related documents.</small>
                </div>
            `;
            return;
        }

        resultsContainer.innerHTML = `
            <div class="search-meta-bar">
                Found <strong>${data.results.length}</strong> highly relevant matches (sorted by semantic similarity):
            </div>
            ${data.results.map((result, idx) => `
                <div class="search-result-card">
                    <div class="result-header">
                        <div class="result-file-info">
                            <span class="result-icon">📄</span>
                            <span class="result-filename">${escapeHTML(result.filename)}</span>
                            <span class="result-page-badge">Page ${result.page}</span>
                        </div>
                        <span class="similarity-badge">
                            ${result.similarity}% match
                        </span>
                    </div>

                    <!-- Short relevant snippet -->
                    <div class="result-snippet">
                        <strong>Snippet:</strong> "${escapeHTML(result.snippet)}"
                    </div>

                    <!-- Expandable full content -->
                    <div id="fulltext-${idx}" class="result-full-text" style="display: none;">
                        <div class="full-text-heading">Complete Content:</div>
                        ${escapeHTML(result.text)}
                    </div>

                    <div class="result-footer">
                        <button
                            type="button"
                            class="view-more-btn"
                            id="viewBtn-${idx}"
                            onclick="toggleSnippetView(${idx})"
                        >
                            View More ↓
                        </button>
                    </div>
                </div>
            `).join("")}
        `;

    } catch (error) {
        console.error(error);
        resultsContainer.innerHTML = `
            <div class="empty-state">
                Search failed: ${escapeHTML(error.message)}
            </div>
        `;
    }
}


function toggleSnippetView(index) {
    const fullTextDiv = document.getElementById(`fulltext-${index}`);
    const toggleBtn = document.getElementById(`viewBtn-${index}`);

    if (!fullTextDiv || !toggleBtn) return;

    if (fullTextDiv.style.display === "none") {
        fullTextDiv.style.display = "block";
        toggleBtn.textContent = "View Less ↑";
        toggleBtn.classList.add("active");
    } else {
        fullTextDiv.style.display = "none";
        toggleBtn.textContent = "View More ↓";
        toggleBtn.classList.remove("active");
    }
}


// ==========================================
// VOICE INPUT (SPEECH RECOGNITION)
// ==========================================

function initSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        console.warn("Speech Recognition API not supported in this browser.");
        return null;
    }

    const reco = new SpeechRecognition();
    reco.continuous = false;
    reco.interimResults = true;
    reco.lang = "en-US";

    reco.onstart = function () {
        isListening = true;
        updateVoiceInputUI(true);
    };

    reco.onresult = function (event) {
        let transcript = "";
        for (let i = event.resultIndex; i < event.results.length; ++i) {
            transcript += event.results[i][0].transcript;
        }

        const input = document.getElementById("questionInput");
        input.value = transcript;
        input.focus();
    };

    reco.onerror = function (event) {
        console.error("Speech recognition error:", event.error);
        stopVoiceRecognition();
        const banner = document.getElementById("voiceStatusBanner");
        if (event.error === "not-allowed") {
            alert("Microphone permission was denied. Please allow microphone access in your browser settings.");
        }
    };

    reco.onend = function () {
        isListening = false;
        updateVoiceInputUI(false);
    };

    return reco;
}


function toggleVoiceRecognition() {
    if (!recognition) {
        recognition = initSpeechRecognition();
    }

    if (!recognition) {
        alert("Speech Recognition is not supported by your current browser. Please use Chrome, Edge, or a Web Speech-compatible browser.");
        return;
    }

    if (isListening) {
        stopVoiceRecognition();
    } else {
        startVoiceRecognition();
    }
}


function startVoiceRecognition() {
    if (!recognition) {
        recognition = initSpeechRecognition();
    }
    if (!recognition) return;

    try {
        recognition.start();
    } catch (err) {
        console.warn("Recognition start warning:", err);
    }
}


function stopVoiceRecognition() {
    if (recognition && isListening) {
        try {
            recognition.stop();
        } catch (err) {
            console.warn("Recognition stop warning:", err);
        }
    }
    isListening = false;
    updateVoiceInputUI(false);
}


function updateVoiceInputUI(listening) {
    const micBtn = document.getElementById("micBtn");
    const micIcon = document.getElementById("micIcon");
    const micLabel = document.getElementById("micLabel");
    const banner = document.getElementById("voiceStatusBanner");

    if (listening) {
        micBtn.classList.add("listening");
        micIcon.textContent = "🔴";
        micLabel.textContent = "Listening...";
        banner.style.display = "flex";
    } else {
        micBtn.classList.remove("listening");
        micIcon.textContent = "🎙️";
        micLabel.textContent = "Speak";
        banner.style.display = "none";
    }
}


// ==========================================
// VOICE OUTPUT (SPEECH SYNTHESIS)
// ==========================================

function playVoice(msgId, text) {
    if (!("speechSynthesis" in window)) {
        alert("Speech synthesis is not supported in this browser.");
        return;
    }

    // Stop existing speech
    window.speechSynthesis.cancel();

    // Clean text of markdown symbols for speech
    const cleanSpeechText = text
        .replace(/^[•\-\*]\s+/gm, "")
        .replace(/Based on your (uploaded )?documents:\s*/gi, "")
        .replace(/\n+/g, ". ")
        .trim();

    const utterance = new SpeechSynthesisUtterance(cleanSpeechText);
    utterance.lang = "en-US";
    utterance.rate = 1.0;
    utterance.pitch = 1.0;

    currentUtterance = utterance;
    currentSpeakingMsgId = msgId;

    utterance.onstart = () => {
        updateVoiceControlsState(msgId, "playing");
    };

    utterance.onpause = () => {
        updateVoiceControlsState(msgId, "paused");
    };

    utterance.onresume = () => {
        updateVoiceControlsState(msgId, "playing");
    };

    utterance.onend = () => {
        updateVoiceControlsState(msgId, "stopped");
        currentSpeakingMsgId = null;
    };

    utterance.onerror = (e) => {
        console.error("SpeechSynthesis error:", e);
        updateVoiceControlsState(msgId, "stopped");
        currentSpeakingMsgId = null;
    };

    window.speechSynthesis.speak(utterance);
}


function pauseVoice(msgId) {
    if ("speechSynthesis" in window && window.speechSynthesis.speaking) {
        window.speechSynthesis.pause();
        updateVoiceControlsState(msgId, "paused");
    }
}


function resumeVoice(msgId) {
    if ("speechSynthesis" in window && window.speechSynthesis.paused) {
        window.speechSynthesis.resume();
        updateVoiceControlsState(msgId, "playing");
    }
}


function stopVoice(msgId) {
    if ("speechSynthesis" in window) {
        window.speechSynthesis.cancel();
        updateVoiceControlsState(msgId, "stopped");
        currentSpeakingMsgId = null;
    }
}


function replayVoice(msgId, text) {
    stopVoice(msgId);
    playVoice(msgId, text);
}


function updateVoiceControlsState(msgId, state) {
    const playBtn = document.getElementById(`vPlay-${msgId}`);
    const pauseBtn = document.getElementById(`vPause-${msgId}`);
    const resumeBtn = document.getElementById(`vResume-${msgId}`);
    const stopBtn = document.getElementById(`vStop-${msgId}`);
    const replayBtn = document.getElementById(`vReplay-${msgId}`);
    const activeBadge = document.getElementById(`vBadge-${msgId}`);

    if (!playBtn) return;

    if (state === "playing") {
        playBtn.style.display = "none";
        pauseBtn.style.display = "inline-flex";
        resumeBtn.style.display = "none";
        stopBtn.style.display = "inline-flex";
        replayBtn.style.display = "none";
        if (activeBadge) activeBadge.style.display = "inline-flex";
    } else if (state === "paused") {
        playBtn.style.display = "none";
        pauseBtn.style.display = "none";
        resumeBtn.style.display = "inline-flex";
        stopBtn.style.display = "inline-flex";
        replayBtn.style.display = "none";
        if (activeBadge) activeBadge.style.display = "inline-flex";
    } else { // stopped
        playBtn.style.display = "inline-flex";
        pauseBtn.style.display = "none";
        resumeBtn.style.display = "none";
        stopBtn.style.display = "none";
        replayBtn.style.display = "inline-flex";
        if (activeBadge) activeBadge.style.display = "none";
    }
}


// ==========================================
// CONCISE AI ASSISTANT & MISSING KNOWLEDGE
// ==========================================

async function askAI() {
    const input = document.getElementById("questionInput");
    const question = input.value.trim();
    const chatArea = document.getElementById("chatArea");
    const message = document.getElementById("askMessage");

    if (!question) {
        message.textContent = "Please enter or speak a question.";
        return;
    }
    message.textContent = "";

    // Stop voice recognition if it was running
    stopVoiceRecognition();

    // Remove welcome card if present
    const welcome = chatArea.querySelector(".assistant-welcome");
    if (welcome) {
        welcome.remove();
    }

    // Display user question
    const userMessage = document.createElement("div");
    userMessage.className = "user-message";
    userMessage.textContent = question;
    chatArea.appendChild(userMessage);

    input.value = "";

    // Loading indicator
    const loading = document.createElement("div");
    loading.className = "ai-loading-box";
    loading.innerHTML = `
        <span class="searching-spinner"></span>
        <span>Searching documents and formulating concise grounded answer...</span>
    `;
    chatArea.appendChild(loading);
    chatArea.scrollTop = chatArea.scrollHeight;

    aiMessageCounter++;
    const currentId = aiMessageCounter;

    try {
        const response = await fetch(`${API_URL}/api/ask`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                question: question,
                threshold: 0.35
            })
        });

        const data = await response.json();
        loading.remove();

        if (!response.ok) {
            throw new Error(data.detail || "AI request failed");
        }

        // ==========================================
        // CASE A: MISSING KNOWLEDGE DETECTION
        // ==========================================
        if (data.knowledge_found === false) {
            const missingCard = document.createElement("div");
            missingCard.className = "knowledge-not-found-card";

            missingCard.innerHTML = `
                <div class="knf-header">
                    <span class="knf-icon">⚠️</span>
                    <div>
                        <h4 class="knf-title">${escapeHTML(data.title || "Knowledge Not Found")}</h4>
                        <p class="knf-message">${escapeHTML(data.message || "No sufficiently relevant information was found in your uploaded documents.")}</p>
                    </div>
                </div>

                <div class="knf-meta-row">
                    <span class="knf-score-chip">
                        Best relevance score: <strong>${data.best_score || 0}%</strong> (Required: ${data.threshold || 35}%)
                    </span>
                </div>

                <div class="knf-suggestion">
                    💡 <strong>Suggestion:</strong> ${escapeHTML(data.suggestion || "Please upload a document covering this topic or try rephrasing your question.")}
                </div>

                <div class="knf-action-row">
                    <button class="primary-btn sm-btn" onclick="showSection('documents')">
                        Go to Upload Document →
                    </button>
                </div>
            `;

            chatArea.appendChild(missingCard);
            chatArea.scrollTop = chatArea.scrollHeight;
            return;
        }

        // ==========================================
        // CASE B: CONCISE AI ANSWER FOUND
        // ==========================================
        const aiMessage = document.createElement("div");
        aiMessage.className = "ai-answer-card";

        const rawAnswerText = data.answer || "";
        const escapedAnswer = escapeHTML(rawAnswerText).replace(/\n/g, "<br>");
        const jsEscapedAnswer = rawAnswerText.replace(/\\/g, "\\\\").replace(/'/g, "\\'").replace(/"/g, '\\"').replace(/\n/g, " ");

        // Sources HTML
        let sourcesHtml = "";
        if (data.sources && data.sources.length > 0) {
            sourcesHtml = `
                <div class="answer-sources">
                    <span class="sources-title">Verified Sources:</span>
                    <div class="sources-pills">
                        ${data.sources.map(s => `
                            <span class="source-pill">
                                📄 ${escapeHTML(s.filename)} (Page ${s.page})
                            </span>
                        `).join("")}
                    </div>
                </div>
            `;
        }

        aiMessage.innerHTML = `
            <div class="ai-card-header">
                <div class="ai-badge">
                    <span>✦</span> DocuMind Concise Answer
                </div>
                <span id="vBadge-${currentId}" class="speaking-badge" style="display: none;">
                    🔊 Speaking...
                </span>
            </div>

            <div class="ai-answer-content">
                ${escapedAnswer}
            </div>

            <!-- Voice Controls Toolbar -->
            <div class="voice-controls-toolbar">
                <button
                    type="button"
                    id="vPlay-${currentId}"
                    class="voice-ctrl-btn read-btn"
                    onclick="playVoice(${currentId}, '${jsEscapedAnswer}')"
                >
                    ▶ Read Answer
                </button>

                <button
                    type="button"
                    id="vPause-${currentId}"
                    class="voice-ctrl-btn"
                    style="display: none;"
                    onclick="pauseVoice(${currentId})"
                >
                    ⏸ Pause
                </button>

                <button
                    type="button"
                    id="vResume-${currentId}"
                    class="voice-ctrl-btn"
                    style="display: none;"
                    onclick="resumeVoice(${currentId})"
                >
                    ▶ Resume
                </button>

                <button
                    type="button"
                    id="vStop-${currentId}"
                    class="voice-ctrl-btn stop-btn"
                    style="display: none;"
                    onclick="stopVoice(${currentId})"
                >
                    ⏹ Stop
                </button>

                <button
                    type="button"
                    id="vReplay-${currentId}"
                    class="voice-ctrl-btn"
                    style="display: none;"
                    onclick="replayVoice(${currentId}, '${jsEscapedAnswer}')"
                >
                    ↺ Replay
                </button>
            </div>

            ${sourcesHtml}
        `;

        chatArea.appendChild(aiMessage);
        chatArea.scrollTop = chatArea.scrollHeight;

    } catch (error) {
        console.error(error);
        loading.remove();
        const errMessage = document.createElement("div");
        errMessage.className = "message error";
        errMessage.textContent = "Error: " + error.message;
        chatArea.appendChild(errMessage);
    }
}


// ==========================================
// HELPER FUNCTIONS
// ==========================================

function getFileIcon(type) {
    if (type === "PDF") return "PDF";
    if (type === "DOCX") return "DOC";
    return "TXT";
}


function formatFileSize(bytes) {
    if (!bytes || isNaN(bytes)) return "0 B";
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}


function escapeHTML(text) {
    if (!text) return "";
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}


// ==========================================
// INITIALIZE APPLICATION
// ==========================================

window.addEventListener("DOMContentLoaded", () => {
    checkBackend();
    loadDocuments();

    // Check speech recognition capability
    if (!("webkitSpeechRecognition" in window) && !("SpeechRecognition" in window)) {
        const micBtn = document.getElementById("micBtn");
        if (micBtn) {
            micBtn.title = "Speech recognition is not supported in this browser";
            micBtn.style.opacity = "0.7";
        }
    }
});