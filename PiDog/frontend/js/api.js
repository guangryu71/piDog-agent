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
    chat(message, sessionId = null) {
        return this._fetch('POST', '/api/chat', { message, session_id: sessionId, stream: false });
    },

    chatStreamUrl(message, sessionId = null) {
        return fetch(API_BASE + '/api/chat/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, session_id: sessionId, stream: true }),
        });
    },

    getSessions() { return this._fetch('GET', '/api/chat/sessions'); },
    deleteSession(id) { return this._fetch('DELETE', `/api/chat/sessions/${id}`); },
    compactSession(id) { return this._fetch('POST', `/api/chat/sessions/${id}/compact`); },

    // ---- Model ----
    getModelStatus() { return this._fetch('GET', '/api/model'); },
    switchModel(provider, model = null, apiKey = null) {
        return this._fetch('POST', '/api/model/switch', { provider, model, api_key: apiKey });
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
};
