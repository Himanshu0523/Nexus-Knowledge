document.addEventListener('DOMContentLoaded', () => {
    // Nav Elements
    const navChat = document.getElementById('btn-nav-chat');
    const navTools = document.getElementById('btn-nav-tools');
    const navData = document.getElementById('btn-nav-data');
    
    // View Elements
    const viewChat = document.getElementById('view-chat');
    const viewTools = document.getElementById('view-tools');
    const viewData = document.getElementById('view-data');
    const viewTitle = document.getElementById('view-title');
    
    // Globals
    const apiKeyInput = document.getElementById('api-key');
    const tenantSelect = document.getElementById('tenant');
    const BASE_URL = 'http://localhost:8000/api/v1';

    // --- NAVIGATION LOGIC ---
    function switchView(viewId, title) {
        document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
        document.querySelectorAll('.view-section').forEach(el => el.classList.remove('active'));
        
        document.getElementById(viewId).classList.add('active');
        viewTitle.innerText = title;
    }

    navChat.addEventListener('click', () => {
        navChat.classList.add('active');
        switchView('view-chat', 'Agent Workspace');
        // Generate new convo ID when explicitly clicking new chat
        window.conversationId = 'conv_' + Math.random().toString(36).substr(2, 9);
        document.getElementById('chat-thread').innerHTML = `
            <div class="message-wrapper system">
                <div class="avatar system">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 2 7 12 12 22 7 12 2"></polygon><polyline points="2 17 12 22 22 17"></polyline><polyline points="2 12 12 17 22 12"></polyline></svg>
                </div>
                <div class="message-bubble content-container">
                    <p>Started a new conversation session.</p>
                </div>
            </div>
        `;
    });

    navTools.addEventListener('click', () => {
        navTools.classList.add('active');
        switchView('view-tools', 'Agents & Tools Directory');
        loadTools();
    });

    navData.addEventListener('click', () => {
        navData.classList.add('active');
        switchView('view-data', 'Data Integration (RAG)');
        loadDocuments();
    });

    // --- CHAT LOGIC ---
    const chatForm = document.getElementById('msg-form');
    const messageInput = document.getElementById('msg-input');
    const chatThread = document.getElementById('chat-thread');
    
    marked.setOptions({
        highlight: function(code, lang) {
            const language = hljs.getLanguage(lang) ? lang : 'plaintext';
            return hljs.highlight(code, { language }).value;
        },
        breaks: true
    });
    
    messageInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 200) + 'px';
        if(this.value === '') this.style.height = 'auto';
    });
    
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            chatForm.dispatchEvent(new Event('submit'));
        }
    });

    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const message = messageInput.value.trim();
        if (!message) return;
        
        const apiKey = apiKeyInput.value.trim();
        const tenant = tenantSelect.value;
        
        messageInput.value = '';
        messageInput.style.height = 'auto';
        
        appendUserMessage(message);
        const loadingId = appendLoadingState();
        
        try {
            if(!window.conversationId) {
                window.conversationId = 'conv_' + Math.random().toString(36).substr(2, 9);
            }

            const response = await fetch(`${BASE_URL}/chat/stream`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${apiKey}`
                },
                body: JSON.stringify({
                    conversation_id: window.conversationId,
                    message: message,
                    metadata: { tenant_id: tenant, client: "web_ui_production" }
                })
            });

            removeElement(loadingId);

            if (!response.ok) {
                let errorMsg = 'Gateway Connection Error';
                try {
                    const err = await response.json();
                    errorMsg = err.error?.message || errorMsg;
                } catch(e) {}
                appendSystemMessage(`**Error:** ${errorMsg}`);
                return;
            }
            
            const responseId = 'msg_' + Date.now();
            const contentEl = createSystemMessageContainer(responseId);
            
            const reader = response.body.getReader();
            const decoder = new TextDecoder('utf-8');
            let fullText = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\n');
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const dataStr = line.slice(6);
                        if (dataStr === '[DONE]') {
                            contentEl.innerHTML = DOMPurify.sanitize(marked.parse(fullText));
                            continue;
                        }
                        
                        try {
                            const data = JSON.parse(dataStr);
                            if (data.type === 'token' && data.token) {
                                fullText += data.token;
                                contentEl.innerHTML = DOMPurify.sanitize(marked.parse(fullText));
                                scrollToBottom();
                            }
                        } catch (e) {
                            console.error('SSE Parse Error:', e, dataStr);
                        }
                    }
                }
            }
        } catch (error) {
            removeElement(loadingId);
            appendSystemMessage('**Connection failed.** Verify that API Gateway is running on port 8000.');
        }
    });

    // --- TOOLS LOGIC ---
    async function loadTools() {
        const tbody = document.getElementById('tools-table-body');
        tbody.innerHTML = '<tr><td colspan="3" style="text-align:center;">Loading tools...</td></tr>';
        
        try {
            const response = await fetch(`${BASE_URL}/tools`, {
                headers: { 'Authorization': `Bearer ${apiKeyInput.value}` }
            });
            
            if(!response.ok) throw new Error("Failed to load");
            const data = await response.json();
            
            if(data.tools && data.tools.length > 0) {
                tbody.innerHTML = data.tools.map(tool => `
                    <tr>
                        <td style="font-weight: 500;">${tool.name}</td>
                        <td style="color: var(--text-secondary);">${tool.description}</td>
                        <td><span class="status-badge" style="font-size: 0.7rem; padding: 2px 8px;">Active</span></td>
                    </tr>
                `).join('');
            } else {
                tbody.innerHTML = '<tr><td colspan="3" style="text-align:center; color: var(--text-secondary);">No tools active.</td></tr>';
            }
        } catch(e) {
            // Handle real API errors
            console.error("Failed to load tools:", e);
            tbody.innerHTML = `<tr><td colspan="3" style="text-align:center; color: var(--danger);">Error connecting to API Gateway: ${e.message}</td></tr>`;
        }
    }

    // --- DATA INTEGRATION LOGIC ---
    const uploadForm = document.getElementById('upload-form');
    const uploadStatus = document.getElementById('upload-status');
    const documentsGrid = document.getElementById('documents-grid');

    async function loadDocuments() {
        documentsGrid.innerHTML = '<div style="color: var(--text-secondary);">Loading documents...</div>';
        try {
            const tenant = tenantSelect.value;
            const response = await fetch(`${BASE_URL}/documents?tenant_id=${tenant}`, {
                headers: { 'Authorization': `Bearer ${apiKeyInput.value}` }
            });
            
            if(!response.ok) throw new Error("Failed to load docs");
            const data = await response.json();
            
            if(data.documents && data.documents.length > 0) {
                documentsGrid.innerHTML = data.documents.map(doc => `
                    <div class="data-item">
                        <div style="font-weight: 500; margin-bottom: 8px; word-break: break-all;">${doc.filename}</div>
                        <div style="font-size: 0.8rem; color: var(--text-secondary);">Status: Indexed</div>
                        <div style="font-size: 0.8rem; color: var(--text-secondary);">ID: ${doc.id}</div>
                    </div>
                `).join('');
            } else {
                documentsGrid.innerHTML = '<div style="color: var(--text-secondary);">No documents indexed for this tenant.</div>';
            }
        } catch (e) {
            // Handle real API errors
            console.error("Failed to load documents:", e);
            documentsGrid.innerHTML = `<div style="color: var(--danger);">Error connecting to API Gateway: ${e.message}</div>`;
        }
    }

    uploadForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const fileInput = document.getElementById('file-upload');
        if(!fileInput.files.length) return;
        
        const file = fileInput.files[0];
        const formData = new FormData();
        formData.append('file', file);
        formData.append('tenant_id', tenantSelect.value);
        
        uploadStatus.innerHTML = '<span style="color: #60a5fa;">Uploading and chunking document...</span>';
        
        try {
            const response = await fetch(`${BASE_URL}/documents`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${apiKeyInput.value}` },
                body: formData
            });
            
            if(!response.ok) throw new Error("Upload failed");
            
            uploadStatus.innerHTML = '<span style="color: var(--success);">Document successfully indexed!</span>';
            fileInput.value = '';
            loadDocuments(); // Refresh grid
            
        } catch (error) {
            console.error("Upload error:", error);
            uploadStatus.innerHTML = `<span style="color: var(--danger);">Upload failed: ${error.message}</span>`;
        }
    });

    // --- UTILS ---
    function appendUserMessage(text) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message-wrapper user`;
        msgDiv.innerHTML = `
            <div class="avatar user">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
            </div>
            <div class="message-bubble">${DOMPurify.sanitize(marked.parse(text))}</div>
        `;
        chatThread.appendChild(msgDiv);
        scrollToBottom();
    }

    function appendSystemMessage(text) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message-wrapper system`;
        msgDiv.innerHTML = `
            <div class="avatar system">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 2 7 12 12 22 7 12 2"></polygon><polyline points="2 17 12 22 22 17"></polyline><polyline points="2 12 12 17 22 12"></polyline></svg>
            </div>
            <div class="message-bubble">${DOMPurify.sanitize(marked.parse(text))}</div>
        `;
        chatThread.appendChild(msgDiv);
        scrollToBottom();
    }

    function createSystemMessageContainer(id) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message-wrapper system`;
        msgDiv.id = id;
        msgDiv.innerHTML = `
            <div class="avatar system">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 2 7 12 12 22 7 12 2"></polygon><polyline points="2 17 12 22 22 17"></polyline><polyline points="2 12 12 17 22 12"></polyline></svg>
            </div>
            <div class="message-bubble content-container"></div>
        `;
        chatThread.appendChild(msgDiv);
        scrollToBottom();
        return msgDiv.querySelector('.content-container');
    }

    function appendLoadingState() {
        const id = 'loading_' + Date.now();
        const msgDiv = document.createElement('div');
        msgDiv.className = `message-wrapper system`;
        msgDiv.id = id;
        msgDiv.innerHTML = `
            <div class="avatar system">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 2 7 12 12 22 7 12 2"></polygon><polyline points="2 17 12 22 22 17"></polyline><polyline points="2 12 12 17 22 12"></polyline></svg>
            </div>
            <div class="message-bubble" style="padding: 12px 24px;">
                <div class="typing-dots">
                    <div class="dot"></div>
                    <div class="dot"></div>
                    <div class="dot"></div>
                </div>
            </div>
        `;
        chatThread.appendChild(msgDiv);
        scrollToBottom();
        return id;
    }

    function removeElement(id) {
        const el = document.getElementById(id);
        if (el) el.remove();
    }

    function scrollToBottom() {
        chatThread.scrollTop = chatThread.scrollHeight;
    }
});
