/* ============================================================
   api.js — 后端 API 封装
   ============================================================ */

const API_BASE = 'http://127.0.0.1:8765';

const api = {
    async _fetch(method, path, body = null) {
        const opts = {
            method,
            headers: { 'Content-Type': 'application/json' },
        };
        if (body) opts.body = JSON.stringify(body);

        const res = await fetch(API_BASE + path, opts);
        if (!res.ok) {
            const text = await res.text();
            throw new Error(`HTTP ${res.status}: ${text}`);
        }
        return res.json();
    },

    // ---- Chat ----
    chat(message, sessionId = null, fileIds = null) {
        return this._fetch('POST', '/api/chat', { message, session_id: sessionId, stream: false, file_ids: fileIds });
    },

    chatStreamUrl(message, sessionId = null, fileIds = null) {
        return fetch(API_BASE + '/api/chat/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, session_id: sessionId, stream: true, file_ids: fileIds }),
        });
    },

    cancelChat(sessionId) {
        return this._fetch('POST', `/api/chat/cancel/${sessionId}`);
    },

    async uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);
        const res = await fetch(API_BASE + '/api/chat/upload', {
            method: 'POST',
            body: formData,
        });
        if (!res.ok) {
            const text = await res.text();
            throw new Error(`HTTP ${res.status}: ${text}`);
        }
        return res.json();
    },

    getSessions() { return this._fetch('GET', '/api/chat/sessions'); },
    getSessionMessages(id) { return this._fetch('GET', `/api/chat/sessions/${id}`); },
    deleteSession(id) { return this._fetch('DELETE', `/api/chat/sessions/${id}`); },
    compactSession(id) { return this._fetch('POST', `/api/chat/sessions/${id}/compact`); },
    approve(taskId, approved) {
        return this._fetch('POST', '/api/chat/approve', { task_id: taskId, approved });
    },
    cleanAllMemory() { return this._fetch('POST', '/api/chat/clean'); },

    // ---- Model ----
    getModelStatus() { return this._fetch('GET', '/api/model'); },
    switchModel(provider, model = null, apiKey = null) {
        return this._fetch('POST', '/api/model/switch', { provider, model, api_key: apiKey });
    },
    saveApiKey(apiKey) {
        return this._fetch('POST', '/api/model/apikey', { provider: '', api_key: apiKey });
    },
    saveOcrApiKey(apiKey) {
        return this._fetch('POST', '/api/model/ocr-apikey', { api_key: apiKey });
    },

    // ---- Tools ----
    getTools() { return this._fetch('GET', '/api/tools'); },

    // ---- Skills ----
    getSkills() { return this._fetch('GET', '/api/skills'); },
    updateSkill(key, data) { return this._fetch('PUT', `/api/skills/${key}`, data); },
    addSkill(key, description) { return this._fetch('POST', '/api/skills', { key, description }); },
    deleteSkill(key) { return this._fetch('DELETE', `/api/skills/${key}`); },

    // ---- Tokens ----
    getTokenStats(days = 30) { return this._fetch('GET', `/api/tokens/stats?days=${days}`); },
    getTokenRecent(limit = 20) { return this._fetch('GET', `/api/tokens/recent?limit=${limit}`); },

    // ---- MCP ----
    getMcpList() { return this._fetch('GET', '/api/mcp'); },
    getMcp(key) { return this._fetch('GET', `/api/mcp/${key}`); },
    operateMcp(key, action, value = null) {
        return this._fetch('POST', '/api/mcp/operate', { key, action, value });
    },
    addMcp(key, name, description = '') {
        return this._fetch('POST', '/api/mcp/add', { key, name, description });
    },

    // ---- ModelScope MCP ----
    modelscopeConnect(name, label, sseUrl) {
        return this._fetch('POST', '/api/mcp/modelscope/connect', { name, label, sse_url: sseUrl });
    },
    modelscopeDisconnect(name) {
        return this._fetch('POST', '/api/mcp/modelscope/disconnect', { name });
    },
    modelscopeSetToken(token) {
        return this._fetch('POST', '/api/mcp/modelscope/token', { token });
    },
    modelscopeGetStatus() { return this._fetch('GET', '/api/mcp/modelscope/status'); },
    modelscopeListConnections() { return this._fetch('GET', '/api/mcp/modelscope/connections'); },
    modelscopeSearch(search = '', category = '', page = 1) {
        return this._fetch('GET', `/api/mcp/modelscope/search?search=${encodeURIComponent(search)}&category=${encodeURIComponent(category)}&page=${page}`);
    },
    modelscopeCategories() { return this._fetch('GET', '/api/mcp/modelscope/categories'); },
    modelscopeDeploy(serverId, envInfo = null) {
        return this._fetch('POST', `/api/mcp/modelscope/deploy/${encodeURIComponent(serverId)}`, { env_info: envInfo });
    },
};
