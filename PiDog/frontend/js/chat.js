/* ============================================================
   chat.js — 对话页面：SSE 流式 + 会话管理 + 停止运行 + 文件上传
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
                <label class="btn btn-sm chat-upload-btn" id="chat-upload-btn" title="Upload file">
                    📎
                </label>
                <input type="file" id="chat-file-input" style="display:none;" multiple>
                <span id="chat-file-indicator" class="chat-file-indicator" style="display:none;"></span>
                <input class="input" id="chat-input" placeholder="Type your message... (Enter to send)" autofocus>
                <button class="btn btn-primary" id="chat-send">Send</button>
                <button class="btn btn-danger chat-stop-btn" id="chat-stop" style="display:none;">⏹ Stop</button>
            </div>
        </div>
    `;

    let sessionId = null;
    let isBusy = false;
    let pendingFileId = null;  // 待发送的文件 ID
    let pendingFileName = null;
    let readerRef = null;      // SSE reader 引用，用于取消
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

    function setBusy(busy) {
        isBusy = busy;
        const sendBtn = document.getElementById('chat-send');
        const stopBtn = document.getElementById('chat-stop');
        const uploadBtn = document.getElementById('chat-upload-btn');

        if (busy) {
            sendBtn.style.display = 'none';
            stopBtn.style.display = '';
            uploadBtn.style.opacity = '0.4';
            uploadBtn.style.pointerEvents = 'none';
        } else {
            sendBtn.style.display = '';
            stopBtn.style.display = 'none';
            uploadBtn.style.opacity = '';
            uploadBtn.style.pointerEvents = '';
            sendBtn.textContent = 'Send';
            sendBtn.disabled = false;
        }
    }

    async function stopRunning() {
        if (!sessionId) return;
        try {
            await api.cancelChat(sessionId);
        } catch (e) {
            // ignore
        }
        // 中断 SSE reader
        if (readerRef) {
            try { readerRef.cancel(); } catch (_) {}
            readerRef = null;
        }
        setBusy(false);
        input.focus();
    }

    async function sendMessage() {
        const text = input.value.trim();
        if (!text || isBusy) return;

        // ---- 命令：/clean ----
        if (text === '/clean') {
            input.value = '';
            addMsg('user', text);
            addMsg('system', '🔄 正在清理所有记忆...');
            try {
                const r = await api.cleanAllMemory();
                if (r.ok) {
                    addMsg('system', `✅ 已清理 ${r.deleted_files} 个文件，内存缓存已清除。`);
                    // 同时清空聊天区域
                    clearMessages();
                    sessionId = null;
                    setSession(null);
                    msgContainer.innerHTML = '<div style="text-align:center;color:var(--text-dim);margin-top:80px;font-size:13px;">🐕 记忆已清理。重新开始吧。</div>';
                } else {
                    addMsg('system', `❌ 清理失败`, 'error');
                }
            } catch (e) {
                addMsg('system', `❌ 清理出错: ${escapeHtml(e.message)}`, 'error');
            }
            setBusy(false);
            input.focus();
            return;
        }

        input.value = '';
        setBusy(true);

        if (msgContainer.children.length === 1 && msgContainer.children[0].tagName === 'DIV') {
            clearMessages();
        }

        // 构建显示文本
        let displayText = text;
        if (pendingFileId) {
            displayText = `📎 ${pendingFileName || 'file'}\n${text}`;
        }
        addMsg('user', displayText);

        try {
            const res = await api.chatStreamUrl(text, sessionId, pendingFileId);

            // 发送后清除文件状态
            pendingFileId = null;
            pendingFileName = null;
            updateFileIndicator();

            const reader = res.body.getReader();
            readerRef = reader;
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
            if (e.name !== 'AbortError') {
                addMsg('assistant', 'Connection failed: ' + e.message, 'error');
            }
        }

        readerRef = null;
        setBusy(false);
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
            case 'tool_result':
                const resultPreview = evt.result ? evt.result.slice(0, 200) : '';
                addMsg('tool', `📊 ${evt.tool} 返回: ${resultPreview}${evt.result && evt.result.length > 200 ? '...' : ''}`);
                break;
            case 'tool_error':
                addMsg('tool', `❌ ${evt.tool}: ${evt.error}`, 'error');
                break;
            case 'approval_required':
                showApprovalDialog(evt.tool, evt.task_id, evt.args);
                break;
            case 'approval_result':
                const ad = document.getElementById(`approval-${evt.task_id}`);
                if (ad) {
                    ad.innerHTML = evt.approved
                        ? '<span style="color:var(--green);font-weight:600;">✅ Approved</span>'
                        : '<span style="color:var(--red);font-weight:600;">❌ Rejected</span>';
                }
                break;
            case 'finish':
                let finishContent = evt.reply || evt.summary;
                if (evt.tool_data && evt.tool_data.length > 80) {
                    finishContent = evt.tool_data + '\n\n━━━ 总结 ━━━\n' + finishContent;
                }
                addMsg('assistant', finishContent);
                break;
            case 'reply':
                addMsg('assistant', evt.content);
                break;
            case 'cancelled':
                addMsg('assistant', '⏹ Task cancelled', 'cancelled');
                break;
        }
    }

    // ---- Approval Dialog ----
    function showApprovalDialog(toolName, taskId, args) {
        // 移除旧审批弹窗
        const old = document.getElementById('approval-bar');
        if (old) old.remove();

        const argsStr = args ? JSON.stringify(args, null, 2) : '{}';
        const bar = document.createElement('div');
        bar.id = 'approval-bar';
        bar.style.cssText = `
            position:sticky; bottom:0; left:0; right:0;
            background:var(--card-bg); border:1px solid var(--yellow);
            border-radius:var(--radius); padding:12px 16px;
            margin-top:8px; z-index:10;
            display:flex; align-items:center; justify-content:space-between; gap:12px;
        `;
        bar.innerHTML = `
            <div style="flex:1;font-size:13px;">
                <strong style="color:var(--yellow);">🔍 需要审批</strong>
                <span style="color:var(--text-dim);">  Agent 想执行：</span>
                <code style="color:var(--accent);">${escapeHtml(toolName)}</code>
                <span id="approval-${taskId}" style="margin-left:8px;"></span>
            </div>
            <div style="display:flex;gap:6px;flex-shrink:0;">
                <button class="btn btn-sm btn-danger" data-approve="no" data-task="${taskId}" style="border-color:var(--red);color:var(--red);">❌ 拒绝</button>
                <button class="btn btn-sm btn-primary" data-approve="yes" data-task="${taskId}">✅ 批准</button>
            </div>
        `;
        msgContainer.appendChild(bar);
        msgContainer.scrollTop = msgContainer.scrollHeight;

        // 批准按钮
        bar.querySelector('[data-approve="yes"]').addEventListener('click', async function () {
            this.textContent = '⏳';
            this.disabled = true;
            try { await api.approve(taskId, true); } catch (e) { /* ignore */ }
        });

        // 拒绝按钮
        bar.querySelector('[data-approve="no"]').addEventListener('click', async function () {
            this.textContent = '⏳';
            this.disabled = true;
            try { await api.approve(taskId, false); } catch (e) { /* ignore */ }
        });
    }

    // ---- File Upload ----
    function updateFileIndicator() {
        const indicator = document.getElementById('chat-file-indicator');
        if (pendingFileId && pendingFileName) {
            indicator.textContent = `📎 ${pendingFileName}`;
            indicator.style.display = '';
        } else {
            indicator.textContent = '';
            indicator.style.display = 'none';
        }
    }

    document.getElementById('chat-file-input').addEventListener('change', async function () {
        const files = this.files;
        if (!files || files.length === 0) return;

        const file = files[0]; // 取第一个文件
        try {
            const result = await api.uploadFile(file);
            if (result.ok) {
                pendingFileId = result.file_id;
                pendingFileName = result.filename;
                updateFileIndicator();
            }
        } catch (e) {
            addMsg('assistant', 'File upload failed: ' + e.message, 'error');
        }
        this.value = ''; // 清空 input，允许重复上传同一文件
    });

    // ---- Event Listeners ----
    document.getElementById('chat-send').addEventListener('click', sendMessage);
    document.getElementById('chat-stop').addEventListener('click', stopRunning);
    document.getElementById('chat-upload-btn').addEventListener('click', () => {
        document.getElementById('chat-file-input').click();
    });

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // New Session
    document.getElementById('chat-new-session').addEventListener('click', () => {
        // 中断当前运行
        if (isBusy) {
            stopRunning();
        }
        sessionId = null;
        setSession(null);
        clearMessages();
        msgContainer.innerHTML = '<div style="text-align:center;color:var(--text-dim);margin-top:80px;font-size:13px;">🐕 New session. Ask me anything.</div>';
    });

    // Compact
    document.getElementById('chat-compact').addEventListener('click', async () => {
        if (!sessionId) return;
        document.getElementById('chat-compact').textContent = '⏳';
        try {
            const result = await api.compactSession(sessionId);
            if (result.ok) {
                addMsg('system', 'Session compacted (old messages summarized)');
            }
        } catch (e) {
            addMsg('system', 'Compact failed: ' + e.message, 'error');
        }
        document.getElementById('chat-compact').textContent = '🗜 Compact';
    });

    // Sessions History
    document.getElementById('chat-sessions-btn').addEventListener('click', async () => {
        try {
            const sessions = await api.getSessions();
            let html = '<h3>📋 会话历史</h3>';
            if (sessions.length === 0) {
                html += '<p style="color:var(--text-dim);padding:20px 0;text-align:center;">暂无会话记录</p>';
            } else {
                html += '<div class="table-wrap"><table><thead><tr><th>ID</th><th>消息</th><th>最后活跃</th><th>预览（用户问题）</th><th>操作</th></tr></thead><tbody>';
                sessions.forEach(s => {
                    const time = window.fmtTime ? window.fmtTime(s.last_active * 1000) : s.last_active;
                    html += `<tr>
                        <td><span class="mono" style="color:var(--accent);cursor:pointer;"
                                onclick="closeModal();loadSession('${s.session_id}');">${s.session_id}</span></td>
                        <td>${s.message_count}</td>
                        <td style="white-space:nowrap;">${time}</td>
                        <td style="max-width:200px;">${window.escapeHtml(s.preview || '(empty)')}</td>
                        <td>
                            <button class="btn btn-sm btn-danger" onclick="api.deleteSession('${s.session_id}').then(()=>document.getElementById('chat-sessions-btn').click())">🗑</button>
                        </td>
                    </tr>`;
                });
                html += '</tbody></table></div>';
            }
            // 直接用 modal 弹窗，不加通用 Confirm 按钮
            document.getElementById('modal-content').innerHTML = html + `
                <div class="modal-actions">
                    <button class="btn" onclick="closeModal()">关闭</button>
                </div>`;
            document.getElementById('modal-overlay').classList.add('show');
        } catch (e) {
            document.getElementById('modal-content').innerHTML = `<p>加载失败: ${escapeHtml(e.message)}</p>
                <div class="modal-actions">
                    <button class="btn" onclick="closeModal()">关闭</button>
                </div>`;
            document.getElementById('modal-overlay').classList.add('show');
        }
    });

    // 全局：加载会话（供 onclick 调用）
    window.loadSession = function (sid) {
        if (isBusy) stopRunning();
        sessionId = sid;
        sessionIdEl.textContent = sid;
        // 尝试加载历史消息
        // 目前只设置 session ID，后续对话会自动恢复历史
        addMsg('system', `已切换到会话 ${sid}`);
    };
}
