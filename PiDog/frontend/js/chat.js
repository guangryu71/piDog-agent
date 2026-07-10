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

        // ---- 命令：/clean_session 删除当前会话 ----
        if (text === '/clean_session') {
            input.value = '';
            addMsg('user', text);
            if (!sessionId) {
                addMsg('system', '⚠️ 当前没有活跃会话，无需清理。');
                setBusy(false);
                input.focus();
                return;
            }
            try {
                await api.deleteSession(sessionId);
                addMsg('system', `✅ 已删除会话 ${sessionId}。`);
                sessionId = null;
                setSession(null);
                clearMessages();
                Object.keys(_pendingCards).forEach(k => delete _pendingCards[k]);
                _textCard = null;
                _textCardIter = -1;
                msgContainer.innerHTML = '<div style="text-align:center;color:var(--text-dim);margin-top:80px;font-size:13px;">🐕 会话已删除。开始新的对话吧。</div>';
            } catch (e) {
                addMsg('system', `❌ 删除失败: ${escapeHtml(e.message)}`, 'error');
            }
            setBusy(false);
            input.focus();
            return;
        }

        // ---- 命令：/compact 压缩当前会话 ----
        if (text === '/compact') {
            input.value = '';
            addMsg('user', text);
            if (!sessionId) {
                addMsg('system', '⚠️ 当前没有活跃会话，无法压缩。');
                setBusy(false);
                input.focus();
                return;
            }
            addMsg('system', '⏳ 正在压缩会话...');
            try {
                const result = await api.compactSession(sessionId);
                if (result.ok) {
                    addMsg('system', '✅ 会话已压缩（旧消息转为摘要）。');
                } else {
                    addMsg('system', '❌ 压缩未完成。');
                }
            } catch (e) {
                addMsg('system', `❌ 压缩失败: ${escapeHtml(e.message)}`, 'error');
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

        // 🧹 重置流式渲染状态，防止下一轮迭代复用上一轮的卡片 key 导致显示覆盖
        Object.keys(_pendingCards).forEach(k => delete _pendingCards[k]);
        _textCard = null;
        _textCardIter = -1;

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

            // ===== 🚀 渐进式工具卡片渲染 =====
            case 'tool_stream_start':
                // 工具调用刚开始 —— 立即创建占位卡片（框先出来）
                _createToolCard(evt.iteration, evt.tool_index);
                break;

            case 'tool_stream_name':
                // 工具名解析到 —— 填入卡片标题
                _updateToolCard(evt.iteration, evt.tool_index, {
                    name: evt.name,
                });
                break;

            case 'tool_stream_args':
                // 参数逐 token 到达 —— 追加到卡片内容区
                _appendToolArgs(evt.iteration, evt.tool_index, evt.delta);
                break;

            case 'text_stream':
                // LLM 纯文本流（非工具调用场景）
                const textCard = _getOrCreateTextCard(evt.iteration);
                textCard.textContent += evt.delta;
                msgContainer.scrollTop = msgContainer.scrollHeight;
                break;

            // ===== 原有事件（不变） =====
            case 'tool_call':
                // 工具开始执行 —— 标记工具卡片为"执行中"
                _markToolExecuting(evt.iteration, evt.tool);
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
                // 查找当前轮次中最后一条 ASSISTANT 消息（来自 text_stream），更新它而非新建
                const assistantMsgs = msgContainer.querySelectorAll('.chat-msg.assistant');
                let lastBody = null;
                if (assistantMsgs.length > 0) {
                    lastBody = assistantMsgs[assistantMsgs.length - 1].querySelector('.chat-msg-content');
                }
                if (lastBody && lastBody.textContent.trim() && 
                    (evt.reply && lastBody.textContent.includes(evt.reply.slice(0, 30)) ||
                     evt.summary && lastBody.textContent.includes(evt.summary.slice(0, 30)))) {
                    // 文本已通过 text_stream 输出，只追加未出现的额外信息
                    const extras = [];
                    if (evt.tool_data && evt.tool_data.length > 80 &&
                        !lastBody.textContent.includes(evt.tool_data.slice(0, 80))) {
                        extras.push(evt.tool_data);
                    }
                    if (evt.summary && !lastBody.textContent.includes(evt.summary)) {
                        extras.push('━━━ 📋 总结 ━━━\n' + evt.summary);
                    }
                    if (extras.length) {
                        lastBody.textContent += '\n\n' + extras.join('\n\n');
                        msgContainer.scrollTop = msgContainer.scrollHeight;
                    }
                } else {
                    let finishContent = evt.reply || evt.summary;
                    if (evt.tool_data && evt.tool_data.length > 80) {
                        finishContent = evt.tool_data + '\n\n━━━ 📋 总结 ━━━\n' + finishContent;
                    }
                    addMsg('assistant', finishContent);
                }
                _textCard = null;
                _textCardIter = -1;
                break;
            case 'reply':
                addMsg('assistant', evt.content);
                break;
            case 'cancelled':
                addMsg('assistant', '⏹ Task cancelled', 'cancelled');
                break;
        }
    }

    // ========== 🚀 渐进渲染辅助函数 ==========

    // 存储待填充的工具卡片 DOM 元素，key: "iter_idx"
    const _pendingCards = {};

    function _createToolCard(iter, toolIdx) {
        const key = `${iter}_${toolIdx}`;
        if (_pendingCards[key]) return;

        const div = document.createElement('div');
        div.className = 'chat-msg tool fade-in';
        div.innerHTML = `<div class="chat-msg-header">TOOL</div>`;
        
        const body = document.createElement('div');
        body.className = 'chat-msg-content tool-card';
        body.innerHTML = `<span class="tool-card-icon">🔧</span>
                          <span class="tool-card-name" style="color:var(--accent);font-weight:600;">...</span>
                          <pre class="tool-card-args" style="margin:4px 0 0 0;font-size:12px;color:var(--text-dim);white-space:pre-wrap;word-break:break-all;"></pre>`;
        
        div.appendChild(body);
        msgContainer.appendChild(div);
        msgContainer.scrollTop = msgContainer.scrollHeight;

        _pendingCards[key] = {
            el: div,
            nameEl: body.querySelector('.tool-card-name'),
            argsEl: body.querySelector('.tool-card-args'),
            iconEl: body.querySelector('.tool-card-icon'),
            name: '',
            args: '',
        };
    }

    function _updateToolCard(iter, toolIdx, data) {
        const key = `${iter}_${toolIdx}`;
        const card = _pendingCards[key];
        if (!card) {
            // 可能 tool_stream_start 事件丢失，补偿创建
            _createToolCard(iter, toolIdx);
            return _updateToolCard(iter, toolIdx, data);
        }
        // 只在首次收到名字时设置，防止模型在同一 tool_index 上发多个工具名导致覆盖
        if (data.name && !card.name) {
            card.name = data.name;
            card.nameEl.textContent = data.name;
            card.iconEl.textContent = '⚡';
        }
    }

    function _appendToolArgs(iter, toolIdx, delta) {
        const key = `${iter}_${toolIdx}`;
        const card = _pendingCards[key];
        if (!card) {
            _createToolCard(iter, toolIdx);
            return _appendToolArgs(iter, toolIdx, delta);
        }
        card.args += delta;
        // finish_task 参数通常包含完整的 reply 文本，只展示摘要避免"结果先于流式"
        const isFinish = card.name === 'finish_task';
        try {
            const parsed = JSON.parse(card.args);
            if (isFinish && parsed.reply) {
                // 只显示 summary + 截断的 reply 预览
                const preview = parsed.reply.length > 50 ? parsed.reply.slice(0, 50) + '...' : parsed.reply;
                card.argsEl.textContent = JSON.stringify({ summary: parsed.summary, reply_preview: preview }, null, 2);
            } else {
                card.argsEl.textContent = JSON.stringify(parsed, null, 2);
            }
        } catch (_) {
            card.argsEl.textContent = card.args;
        }
        msgContainer.scrollTop = msgContainer.scrollHeight;
    }

    function _markToolExecuting(iter, toolName) {
        // 找到最近一个匹配的 pending card 并标记为执行中
        const prefix = `${iter}_`;
        const keys = Object.keys(_pendingCards).filter(k => k.startsWith(prefix));
        // 找最后一个未标记的
        for (let i = keys.length - 1; i >= 0; i--) {
            const card = _pendingCards[keys[i]];
            if (card && !card._executing) {
                card._executing = true;
                card.iconEl.textContent = '🔄';
                card.nameEl.textContent = toolName + ' (executing...)';
                card.nameEl.style.opacity = '0.7';
                return;
            }
        }
    }

    let _textCard = null;
    let _textCardIter = -1;

    function _getOrCreateTextCard(iter) {
        if (_textCard && _textCardIter === iter) return _textCard;
        // 新迭代，创建新文本卡片
        _textCardIter = iter;
        const div = document.createElement('div');
        div.className = 'chat-msg assistant fade-in';
        div.innerHTML = `<div class="chat-msg-header">ASSISTANT</div>`;
        const body = document.createElement('div');
        body.className = 'chat-msg-content';
        div.appendChild(body);
        msgContainer.appendChild(div);
        _textCard = body;
        return body;
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

    // ---- 命令提示（输入 / 时显示可选命令，不提供 Tab 补齐） ----
    const cmdHint = document.createElement('div');
    cmdHint.className = 'cmd-hint';
    cmdHint.style.display = 'none';
    cmdHint.innerHTML = `
        <div class="cmd-hint-item" data-cmd="/clean">
            <span class="cmd-hint-name">/clean</span>
            <span class="cmd-hint-desc">清理所有记忆和会话</span>
        </div>
        <div class="cmd-hint-item" data-cmd="/clean_session">
            <span class="cmd-hint-name">/clean_session</span>
            <span class="cmd-hint-desc">删除当前会话</span>
        </div>
        <div class="cmd-hint-item" data-cmd="/compact">
            <span class="cmd-hint-name">/compact</span>
            <span class="cmd-hint-desc">压缩当前会话（摘要旧消息）</span>
        </div>`;
    input.parentNode.insertBefore(cmdHint, input);

    // 点击提示项 → 填入输入框
    cmdHint.querySelectorAll('.cmd-hint-item').forEach(item => {
        item.addEventListener('click', () => {
            input.value = item.dataset.cmd;
            input.focus();
            cmdHint.style.display = 'none';
        });
    });

    input.addEventListener('input', () => {
        const val = input.value;
        if (val.startsWith('/') && !val.includes(' ')) {
            const items = cmdHint.querySelectorAll('.cmd-hint-item');
            let anyVisible = false;
            items.forEach(item => {
                if (item.dataset.cmd.startsWith(val)) {
                    item.style.display = '';
                    anyVisible = true;
                } else {
                    item.style.display = 'none';
                }
            });
            cmdHint.style.display = anyVisible ? '' : 'none';
        } else {
            cmdHint.style.display = 'none';
        }
    });

    input.addEventListener('blur', () => {
        // 延迟隐藏，让点击事件先触发
        setTimeout(() => { cmdHint.style.display = 'none'; }, 150);
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
        Object.keys(_pendingCards).forEach(k => delete _pendingCards[k]);
        _textCard = null;
        _textCardIter = -1;
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
                    html += `<tr>
                        <td><span class="mono" style="color:var(--accent);cursor:pointer;"
                                onclick="closeModal();loadSession('${s.session_id}');">${s.session_id}</span></td>
                        <td>${s.messages_count}</td>
                        <td style="white-space:nowrap;">${s.last_active}</td>
                        <td style="max-width:200px;">${window.escapeHtml(s.preview || '(empty)')}</td>
                        <td>
                            <button class="btn btn-sm btn-danger" onclick="event.stopPropagation();api.deleteSession('${s.session_id}').then(()=>{closeModal();document.getElementById('chat-sessions-btn').click();})">🗑</button>
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

    // ========== 📋 从后端 session 文件加载历史 ==========

    function renderMessageHistory(messages) {
        // 将后端 session JSON 转换为 DOM 元素
        let lastFinishReply = null;  // 记录最后一个 finish_task 的 reply
        for (const msg of messages) {
            const role = msg.role;
            if (role === 'system') continue;  // 跳过系统消息（压缩摘要等）

            if (role === 'user') {
                let content = msg.content;
                if (Array.isArray(content)) {
                    content = content.filter(c => c.type === 'text').map(c => c.text).join('\n');
                }
                addMsg('user', content || '(empty)');
            }
            else if (role === 'assistant') {
                if (msg.tool_calls) {
                    for (const tc of msg.tool_calls) {
                        const fn = tc.function || {};
                        const div = document.createElement('div');
                        div.className = 'chat-msg tool fade-in';
                        div.innerHTML = `<div class="chat-msg-header">TOOL</div>`;
                        const body = document.createElement('div');
                        body.className = 'chat-msg-content tool-card';
                        let argsDisplay = '';
                        try {
                            const parsed = JSON.parse(fn.arguments || '{}');
                            if (fn.name === 'finish_task') {
                                lastFinishReply = parsed.reply || null;
                                const preview = parsed.reply ? (parsed.reply.length > 50 ? parsed.reply.slice(0, 50) + '...' : parsed.reply) : '';
                                argsDisplay = JSON.stringify({ summary: parsed.summary, reply_preview: preview }, null, 2);
                            } else {
                                argsDisplay = JSON.stringify(parsed, null, 2);
                            }
                        } catch (_) { argsDisplay = fn.arguments || ''; }
                        body.innerHTML = `<span class="tool-card-icon">⚡</span>
                                          <span class="tool-card-name" style="color:var(--accent);font-weight:600;">${escapeHtml(fn.name)}</span>
                                          <pre class="tool-card-args" style="margin:4px 0 0 0;font-size:12px;color:var(--text-dim);white-space:pre-wrap;word-break:break-all;">${escapeHtml(argsDisplay)}</pre>`;
                        div.appendChild(body);
                        msgContainer.appendChild(div);
                    }
                }
                if (msg.content) {
                    addMsg('assistant', msg.content);
                    lastFinishReply = null;  // 已有 assistant 回复，不需要兜底
                }
            }
            else if (role === 'tool') {
                let resultText = msg.content || '';
                try {
                    const r = JSON.parse(resultText);
                    if (r.status === 'success') {
                        resultText = `✅ 执行成功${r.items ? ' (' + r.items.length + ' 项)' : ''}`;
                    } else if (r.error) {
                        resultText = `❌ ${r.error}`;
                    }
                } catch (_) {}
                if (resultText.length > 150) resultText = resultText.slice(0, 150) + '...';
                const div = document.createElement('div');
                div.className = 'chat-msg tool fade-in';
                div.innerHTML = `<div class="chat-msg-header">RESULT</div>`;
                const body = document.createElement('div');
                body.className = 'chat-msg-content';
                body.style.cssText = 'font-size:12px;color:var(--text-dim);';
                body.textContent = resultText;
                div.appendChild(body);
                msgContainer.appendChild(div);
            }
        }
        // 兜底：如果 session 文件末尾没有 assistant 回复，补上 finish_task 的 reply
        if (lastFinishReply) {
            addMsg('assistant', lastFinishReply);
        }
        msgContainer.scrollTop = msgContainer.scrollHeight;
    }

    async function loadSessionHistory(sid) {
        if (isBusy) stopRunning();
        clearMessages();
        _pendingCards && Object.keys(_pendingCards).forEach(k => delete _pendingCards[k]);
        _textCard = null;
        _textCardIter = -1;

        try {
            const data = await api.getSessionMessages(sid);
            const messages = data.messages || [];
            if (messages.length === 0) {
                msgContainer.innerHTML = '<div style="text-align:center;color:var(--text-dim);margin-top:80px;font-size:13px;">🐕 空会话。开始提问吧。</div>';
            } else {
                renderMessageHistory(messages);
            }
            sessionId = sid;
            setSession(sid);
        } catch (e) {
            addMsg('system', `加载会话失败: ${escapeHtml(e.message)}`, 'error');
            sessionId = sid;
            setSession(sid);
        }
    }

    // 全局：加载会话（供 sessions 列表 onclick 调用）
    window.loadSession = function (sid) {
        loadSessionHistory(sid);
    };

    // ---- 首次加载：尝试恢复最近的会话历史 ----
    (async function initSession() {
        try {
            const sessions = await api.getSessions();
            if (sessions && sessions.length > 0) {
                const lastSid = sessions[0].session_id;
                await loadSessionHistory(lastSid);
            }
        } catch (_) {
            // 无法获取历史，使用默认欢迎页
        }
    })();
}
