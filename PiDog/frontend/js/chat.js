/* ============================================================
   chat.js — 对话页面：SSE 流式 + 会话管理 + 压缩
   ============================================================ */

function renderChatPage(container) {
    container.innerHTML = `
        <div class="chat-container">
            <div class="chat-session-bar">
                <span style="font-weight:600;">Session:</span>
                <span class="session-id" id="chat-session-id">—</span>
                <button class="btn btn-sm" id="chat-new-session">+ New</button>
                <button class="btn btn-sm" id="chat-compact">🗜 Compact</button>
                <span style="flex:1;"></span>
                <button class="btn btn-sm" id="chat-sessions-btn">📋 History</button>
            </div>

            <div class="chat-messages" id="chat-messages">
                <div style="text-align:center;color:var(--text-dim);margin-top:80px;font-size:13px;">
                    🐕 PiDog ready. Ask me anything.
                </div>
            </div>

            <div class="chat-input-wrap">
                <input class="input" id="chat-input" placeholder="Type your message... (Enter to send)" autofocus>
                <button class="btn btn-primary" id="chat-send">Send</button>
            </div>
        </div>
    `;

    let sessionId = null;
    let isBusy = false;
    const msgContainer = document.getElementById('chat-messages');
    const input = document.getElementById('chat-input');
    const sessionIdEl = document.getElementById('chat-session-id');

    function addMsg(role, content, extraClass = '') {
        const div = document.createElement('div');
        div.className = `chat-msg ${role} ${extraClass} fade-in`;
        if (role !== 'user') {
            div.innerHTML = `<div class="chat-msg-header">${role.toUpperCase()}</div>`;
        }
        const body = document.createElement('div');
        body.className = 'chat-msg-content';
        body.textContent = content;
        div.appendChild(body);
        msgContainer.appendChild(div);
        msgContainer.scrollTop = msgContainer.scrollHeight;
        return body;
    }

    function setSession(sid) {
        sessionId = sid;
        sessionIdEl.textContent = sid || '—';
    }

    function clearMessages() {
        msgContainer.innerHTML = '';
    }

    async function sendMessage() {
        const text = input.value.trim();
        if (!text || isBusy) return;

        input.value = '';
        isBusy = true;

        document.getElementById('chat-send').disabled = true;
        document.getElementById('chat-send').innerHTML = '<span class="spinner"></span>';

        if (msgContainer.children.length === 1 && msgContainer.children[0].tagName === 'DIV') {
            clearMessages();
        }

        addMsg('user', text);

        try {
            const res = await api.chatStreamUrl(text, sessionId);
            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    const trimmed = line.trim();
                    if (!trimmed || !trimmed.startsWith('data: ')) continue;
                    const data = trimmed.slice(6);
                    if (data === '[DONE]') break;

                    try {
                        const evt = JSON.parse(data);
                        handleStreamEvent(evt);
                    } catch (e) {
                        // skip malformed
                    }
                }
            }
        } catch (e) {
            addMsg('assistant', 'Connection failed: ' + e.message, 'error');
        }

        isBusy = false;
        document.getElementById('chat-send').disabled = false;
        document.getElementById('chat-send').textContent = 'Send';
        input.focus();
    }

    function handleStreamEvent(evt) {
        switch (evt.type) {
            case 'session':
                setSession(evt.session_id);
                break;
            case 'tool_call':
                addMsg('tool', `🔧 ${evt.tool} (step ${evt.iteration})`);
                break;
            case 'tool_error':
                addMsg('tool', `❌ ${evt.tool}: ${evt.error}`, 'error');
                break;
            case 'finish':
                addMsg('assistant', evt.summary);
                break;
            case 'reply':
                addMsg('assistant', evt.content);
                break;
        }
    }

    // ---- Event Listeners ----
    document.getElementById('chat-send').addEventListener('click', sendMessage);
    input.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } });

    document.getElementById('chat-new-session').addEventListener('click', () => {
        setSession(null);
        clearMessages();
        msgContainer.innerHTML = '<div style="text-align:center;color:var(--text-dim);margin-top:80px;font-size:13px;">New session started.</div>';
    });

    document.getElementById('chat-compact').addEventListener('click', async () => {
        if (!sessionId) return alert('No active session');
        try {
            const r = await api.compactSession(sessionId);
            if (r.ok) {
                clearMessages();
                addMsg('tool', `🗜 Compacted: ${r.before} → ${r.after} messages`);
                addMsg('assistant', r.summary);
            } else {
                alert(r.error);
            }
        } catch (e) {
            alert('Compact failed: ' + e.message);
        }
    });

    document.getElementById('chat-sessions-btn').addEventListener('click', async () => {
        try {
            const sessions = await api.getSessions();
            const rows = sessions.map(s => `
                <div class="flex-between mb-8" style="padding:8px 0;border-bottom:1px solid var(--border);">
                    <div>
                        <span class="mono">${s.session_id}</span>
                        <span style="color:var(--text-dim);font-size:11px;">· ${s.messages_count} msgs · ${s.last_active}</span>
                    </div>
                    <div class="gap-8" style="display:flex;">
                        <button class="btn btn-xs" onclick="closeModal(); (function loadSid(sid){ document.getElementById('chat-session-id').textContent=sid; window._chatLoadSession=sid; document.getElementById('chat-messages').innerHTML='<div style=text-align:center;color:var(--text-dim);margin-top:80px>Loaded session: '+sid+'</div>'; document.getElementById('chat-new-session').click(); })('${s.session_id}')">Load</button>
                        <button class="btn btn-xs btn-danger" onclick="api.deleteSession('${s.session_id}').then(()=>{closeModal();document.getElementById('chat-sessions-btn').click();})">Del</button>
                    </div>
                </div>
            `).join('') || '<div style="color:var(--text-dim);">No sessions yet.</div>';
            showModal(`<h3>📋 Sessions</h3><div style="max-height:400px;overflow-y:auto;">${rows}</div>`);
        } catch (e) {
            alert('Failed: ' + e.message);
        }
    });

    input.focus();
}
