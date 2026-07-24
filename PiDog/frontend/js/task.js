/* ============================================================
   task.js — 自定义任务页面
   可创建/编辑/删除/运行自定义任务，支持 skill / MCP / 工具过滤
   ============================================================ */

async function renderTaskPage(container) {
    const [tasks, allTools, skills, mcps] = await Promise.all([
        api.getTasks(),
        api.getTools(),
        api.getSkills().catch(() => []),
        api.getMcpList().catch(() => []),
    ]);
    const CACHE = { allTools, skills, mcps };

    let rows = '';
    if (tasks.length === 0) {
        rows = '<div style="text-align:center;color:var(--text-dim);padding:40px;">暂无任务，点击右上角「添加任务」创建</div>';
    } else {
        rows = tasks.map(function(t) {
            var escapedPrompt = escapeHtml(t.agent_prompt || '');
            var escapedTitle = escapeHtml(t.title || '');
            var toolCount = (t.selected_skills?.length || 0) + (t.selected_tools?.length || 0) + (t.selected_mcp?.length || 0);
            var summary = toolCount > 0 ? '已选 ' + toolCount + ' 项过滤' : '默认全选';
            return '<div class="task-card" data-task-id="' + t.id + '">'
                + '<div class="task-card-row">'
                +   '<div class="task-card-left">'
                +     '<button class="btn btn-sm task-hist-btn" onclick="showTaskHistory(\'' + t.id + '\',\'' + escapedTitle + '\')" title="历史运行结果">📋</button>'
                +   '</div>'
                +   '<div class="task-card-body">'
                +     '<div class="task-card-title">' + escapedTitle + '</div>'
                +     '<div class="task-card-prompt">' + escapedPrompt + '</div>'
                +     '<div class="task-card-summary">' + summary + '</div>'
                +   '</div>'
                +   '<div class="task-card-actions">'
                +     '<button class="btn btn-sm btn-primary task-run-btn" onclick="runTask(\'' + t.id + '\')">▶ 运行</button>'
                +     '<button class="btn btn-sm" onclick="editTask(\'' + t.id + '\')">✎ 编辑</button>'
                +     '<button class="btn btn-sm btn-danger" onclick="deleteTaskConfirm(\'' + t.id + '\')">✕ 删除</button>'
                +   '</div>'
                + '</div>'
                // 行内展开的日志区域（默认隐藏）
                + '<div class="task-log-area" id="task-log-' + t.id + '" style="display:none;">'
                +   '<div class="task-log-content" id="task-log-content-' + t.id + '"></div>'
                +   '<div class="task-log-status" id="task-log-status-' + t.id + '"></div>'
                + '</div>'
                + '</div>';
        }).join('');
    }

    container.innerHTML = ''
        + '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">'
        +   '<h2 style="margin:0;">📋 自定义任务 <span style="color:var(--text-dim);font-size:13px;">（共 ' + tasks.length + ' 个）</span></h2>'
        +   '<button class="btn btn-primary" onclick="showAddTaskModal()">＋ 添加任务</button>'
        + '</div>'
        + '<div class="task-card-list">'
        +   rows
        + '</div>';
}

// ==================== 模态框：添加/编辑任务 ====================

function showAddTaskModal(taskData) {
    var isEdit = !!taskData;
    var title = isEdit ? '编辑任务' : '添加任务';

    if (!window.__taskCache || !window.__taskCache._ready) {
        loadTaskCache().then(function() { showAddTaskModal(taskData); });
        return;
    }
    var CACHE = window.__taskCache;

    var skillChecks = CACHE.skills.map(function(s) {
        var key = s.key || s;
        var label = s.description || s;
        var checked = !isEdit || !taskData.selected_skills?.length || (taskData.selected_skills || []).indexOf(key) >= 0;
        return '<label class="task-check-label"><input type="checkbox" class="task-skill-cb" value="' + escapeHtml(key) + '" ' + (checked ? 'checked' : '') + '> ' + escapeHtml(label) + '</label>';
    }).join('');

    var toolChecks = CACHE.allTools.map(function(t) {
        var checked = !isEdit || !taskData.selected_tools?.length || (taskData.selected_tools || []).indexOf(t.name) >= 0;
        return '<label class="task-check-label"><input type="checkbox" class="task-tool-cb" value="' + escapeHtml(t.name) + '" ' + (checked ? 'checked' : '') + '> ' + escapeHtml(t.name) + '</label>';
    }).join('');

    var mcpChecks = CACHE.mcps.map(function(m) {
        var key = m.key || m.name || m;
        var label = m.name || m.key || m;
        var checked = !isEdit || !taskData.selected_mcp?.length || (taskData.selected_mcp || []).indexOf(key) >= 0;
        return '<label class="task-check-label"><input type="checkbox" class="task-mcp-cb" value="' + escapeHtml(key) + '" ' + (checked ? 'checked' : '') + '> ' + escapeHtml(label) + '</label>';
    }).join('');

    var html = ''
        + '<div style="display:flex;flex-direction:column;height:100%;">'
        +   '<h3 style="margin:0 0 12px 0;">' + title + '</h3>'
        +   '<div style="flex:1;overflow-y:auto;padding-right:4px;">'
        +     '<div class="task-field"><label>标题 <span style="color:var(--red);">*</span> <span style="color:var(--text-dim);font-size:12px;">（仅展示用，不参与对话）</span></label>'
        +       '<input type="text" id="task-title" class="task-input" value="' + escapeHtml(taskData?.title || '') + '" placeholder="例如：代码审查助手"></div>'
        +     '<div class="task-field"><label>Agent 提示词 <span style="color:var(--red);">*</span></label>'
        +       '<textarea id="task-prompt" class="task-textarea" rows="4" placeholder="定义 agent 的行为和任务目标...">' + escapeHtml(taskData?.agent_prompt || '') + '</textarea></div>'
        +     '<div class="task-field"><label>初始对话内容 <span style="color:var(--red);">*</span> <span style="color:var(--text-dim);font-size:12px;">（任务运行时自动发送）</span></label>'
        +       '<textarea id="task-initmsg" class="task-textarea" rows="3" placeholder="任务启动后自动发送的消息...">' + escapeHtml(taskData?.init_message || '') + '</textarea></div>'
        +     '<div class="task-field"><label>上传文件 <span style="color:var(--text-dim);font-size:12px;">（可选，任务运行时可用）</span></label>'
        +       '<input type="file" id="task-file-input" multiple hidden>'
        +       '<div style="display:flex;gap:8px;align-items:center;"><button class="btn btn-sm" id="task-upload-btn" type="button">📎 选择文件</button><span style="font-size:12px;color:var(--text-dim);" id="task-file-count"></span></div>'
        +       '<div id="task-file-list" style="margin-top:6px;display:flex;flex-wrap:wrap;gap:6px;"></div></div>'
        +     '<div style="margin-top:14px;border-top:1px solid var(--border);padding-top:12px;">'
        +       '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;"><strong>工具过滤</strong><span style="font-size:12px;color:var(--text-dim);">默认全选，取消勾选可减少 token 消耗</span></div>'
        +       '<details style="margin-bottom:8px;" open><summary style="cursor:pointer;font-size:13px;color:var(--accent);">📦 Skills（' + CACHE.skills.length + '）</summary>'
        +         '<div style="display:flex;flex-wrap:wrap;gap:4px;padding:6px 0;">' + (skillChecks || '<span style="color:var(--text-dim);font-size:12px;">暂无技能</span>') + '</div></details>'
        +       '<details style="margin-bottom:8px;"><summary style="cursor:pointer;font-size:13px;color:var(--accent);">🔧 Tools（' + CACHE.allTools.length + '）</summary>'
        +         '<div style="display:flex;flex-wrap:wrap;gap:4px;padding:6px 0;">' + (toolChecks || '<span style="color:var(--text-dim);font-size:12px;">暂无工具</span>') + '</div></details>'
        +       '<details style="margin-bottom:8px;"><summary style="cursor:pointer;font-size:13px;color:var(--accent);">🔌 MCP（' + CACHE.mcps.length + '）</summary>'
        +         '<div style="display:flex;flex-wrap:wrap;gap:4px;padding:6px 0;">' + (mcpChecks || '<span style="color:var(--text-dim);font-size:12px;">暂无 MCP</span>') + '</div></details>'
        +     '</div>'
        +   '</div>'
        +   '<div style="display:flex;justify-content:flex-end;gap:8px;margin-top:12px;padding-top:12px;border-top:1px solid var(--border);">'
        +     '<button class="btn" onclick="closeModal()">取消</button>'
        +     '<button class="btn btn-primary" id="task-save-btn">' + (isEdit ? '保存修改' : '添加') + '</button>'
        +   '</div>'
        + '</div>';

    showModal(html, false);

    // ── 文件上传 ──
    var taskFiles = [];
    if (isEdit && taskData.selected_files) {
        taskFiles = taskData.selected_files.map(function(f) { return typeof f === 'string' ? { fileId: f, fileName: f } : f; });
    }
    updateTaskFileList(taskFiles);

    document.getElementById('task-upload-btn').onclick = function() { document.getElementById('task-file-input').click(); };
    document.getElementById('task-file-input').onchange = async function() {
        var files = this.files;
        if (!files || files.length === 0) return;
        for (var i = 0; i < files.length; i++) {
            var file = files[i];
            try {
                var result = await api.uploadFile(file);
                if (result.ok) taskFiles.push({ fileId: result.file_id, fileName: result.filename });
            } catch (e) { alert('上传失败: ' + file.name + ' — ' + e.message); }
        }
        this.value = '';
        updateTaskFileList(taskFiles);
    };

    function updateTaskFileList(files) {
        var listEl = document.getElementById('task-file-list');
        var countEl = document.getElementById('task-file-count');
        if (!listEl) return;
        countEl.textContent = files.length > 0 ? files.length + ' 个文件' : '';
        if (files.length === 0) { listEl.innerHTML = ''; return; }
        var html = '';
        for (var j = 0; j < files.length; j++) {
            var f = files[j];
            html += '<span class="task-check-label" style="padding:2px 6px;">📄 ' + escapeHtml(f.fileName)
                + ' <span class="task-file-del" data-idx="' + j + '" style="cursor:pointer;margin-left:4px;color:var(--red);">✕</span></span>';
        }
        listEl.innerHTML = html;
        listEl.querySelectorAll('.task-file-del').forEach(function(btn) {
            btn.onclick = function() {
                var idx = parseInt(this.dataset.idx);
                taskFiles.splice(idx, 1);
                updateTaskFileList(taskFiles);
            };
        });
    }

    // 保存按钮
    document.getElementById('task-save-btn').onclick = async function() {
        var title = document.getElementById('task-title').value.trim();
        var prompt = document.getElementById('task-prompt').value.trim();
        var initMsg = document.getElementById('task-initmsg').value.trim();
        if (!title) { alert('请输入任务标题'); return; }
        if (!prompt) { alert('请输入 Agent 提示词'); return; }
        if (!initMsg) { alert('请输入初始对话内容'); return; }

        var selectedSkills = Array.from(document.querySelectorAll('.task-skill-cb:checked')).map(function(el) { return el.value; });
        var selectedTools = Array.from(document.querySelectorAll('.task-tool-cb:checked')).map(function(el) { return el.value; });
        var selectedMcp = Array.from(document.querySelectorAll('.task-mcp-cb:checked')).map(function(el) { return el.value; });

        var allSkills = CACHE.skills.map(function(s) { return s.key || s; });
        var allTools = CACHE.allTools.map(function(t) { return t.name; });
        var allMcp = CACHE.mcps.map(function(m) { return m.key || m.name || m; });

        var data = {
            title: title,
            agent_prompt: prompt,
            init_message: initMsg,
            selected_skills: selectedSkills.length === allSkills.length ? [] : selectedSkills,
            selected_tools: selectedTools.length === allTools.length ? [] : selectedTools,
            selected_mcp: selectedMcp.length === allMcp.length ? [] : selectedMcp,
            selected_files: taskFiles.map(function(f) { return f.fileId; }),
        };

        try {
            if (isEdit) { await api.updateTask(taskData.id, data); }
            else { await api.createTask(data); }
            closeModal();
            if (typeof refreshPage === 'function') refreshPage('task');
        } catch (e) { alert('保存失败: ' + e.message); }
    };
}

// ==================== 编辑任务 ====================

function editTask(taskId) {
    api.getTask(taskId).then(function(task) { showAddTaskModal(task); }).catch(function(e) { alert('加载失败: ' + e.message); });
}

// ==================== 删除确认 ====================

function deleteTaskConfirm(taskId) {
    var overlay = document.getElementById('modal-overlay');
    var content = document.getElementById('modal-content');
    content.innerHTML = '<h3>确认删除</h3><p style="color:var(--text-dim);margin:12px 0;">确定要删除此任务吗？此操作不可恢复。</p>'
        + '<div class="modal-actions"><button class="btn" onclick="closeModal()">取消</button><button class="btn btn-danger" id="task-delete-confirm-btn">确认删除</button></div>';
    overlay.classList.add('show');
    document.getElementById('task-delete-confirm-btn').onclick = async function() {
        try { await api.deleteTask(taskId); closeModal(); if (typeof refreshPage === 'function') refreshPage('task'); }
        catch (e) { alert('删除失败: ' + e.message); }
    };
}

// ==================== 运行任务（行内展开日志）====================

var _runningTasks = {};  // {taskId: {sessionId, taskTitle}}

function runTask(taskId) {
    // 如果该任务正在运行 → 停止
    if (_runningTasks[taskId]) {
        stopRunningTask(taskId);
        return;
    }

    // 获取任务详情并启动
    api.getTask(taskId).then(function(task) {
        if (!task) { alert('任务不存在'); return; }
        api.runTask(taskId).then(function(runResult) {
            if (!runResult || !runResult.session_id) { alert('任务启动失败'); return; }

            var sessionId = runResult.session_id;
            var initMessage = task.init_message || '开始执行任务';

            // 切换运行按钮为停止
            setRunButtonState(taskId, 'stop');

            // 展开日志区域
            var logArea = document.getElementById('task-log-' + taskId);
            var logContent = document.getElementById('task-log-content-' + taskId);
            var logStatus = document.getElementById('task-log-status-' + taskId);
            if (logArea) logArea.style.display = '';
            if (logContent) logContent.innerHTML = '<div class="log-line log-line-system">正在启动任务...</div>';
            if (logStatus) logStatus.textContent = '';

            // 记录运行状态
            _runningTasks[taskId] = { sessionId: sessionId, taskTitle: task.title };

            // 启动 SSE 流
            startTaskStream(taskId, sessionId, initMessage, task.selected_files || []);

        }).catch(function(e) { alert('任务启动失败: ' + e.message); });
    }).catch(function(e) { alert('获取任务失败: ' + e.message); });
}

function stopRunningTask(taskId) {
    var rt = _runningTasks[taskId];
    if (!rt) return;
    api.cancelChat(rt.sessionId).catch(function() {});
    delete _runningTasks[taskId];
    setRunButtonState(taskId, 'stopped');
    appendLogLine(taskId, 'system', '⏹ 任务已手动停止');
    finalizeTaskLog(taskId, true);
}

function setRunButtonState(taskId, state) {
    var card = document.querySelector('.task-card[data-task-id="' + taskId + '"]');
    if (!card) return;
    var btn = card.querySelector('.task-run-btn');
    if (!btn) return;
    if (state === 'stop') {
        btn.textContent = '⏹ 停止';
        btn.className = 'btn btn-sm btn-danger task-run-btn';
        btn.onclick = function() { stopRunningTask(taskId); };
    } else if (state === 'stopped') {
        btn.textContent = '▶ 运行';
        btn.className = 'btn btn-sm btn-primary task-run-btn';
        btn.onclick = function() { runTask(taskId); };
    } else if (state === 'done') {
        btn.textContent = '▶ 运行';
        btn.className = 'btn btn-sm btn-primary task-run-btn';
        btn.onclick = function() { runTask(taskId); };
    }
}

// ==================== 日志管理 ====================

// 文本缓冲：累积 text_stream 的 delta，在非 text 事件到达时 flush
var _textBuffer = {};

function flushTextBuffer(taskId) {
    if (!_textBuffer[taskId] || !_textBuffer[taskId].text) return;
    var text = _textBuffer[taskId].text;
    _textBuffer[taskId].text = '';
    if (text) appendLogLine(taskId, 'text', text);
}

function appendLogLine(taskId, type, text) {
    var logContent = document.getElementById('task-log-content-' + taskId);
    if (!logContent) return;

    var colorMap = { text: 'var(--text)', tool: 'var(--accent)', error: 'var(--red)', system: 'var(--green)', result: '#ffd700' };
    var prefixMap = { text: '', tool: '🔧 ', error: '❌ ', system: '💬 ', result: '✅ ' };
    var color = colorMap[type] || 'var(--text-dim)';
    var prefix = prefixMap[type] || '';

    var line = document.createElement('div');
    line.className = 'log-line log-line-' + type;
    line.style.color = color;
    line.textContent = prefix + text;
    logContent.appendChild(line);
    logContent.scrollTop = logContent.scrollHeight;
}

function clearLogContent(taskId) {
    var logContent = document.getElementById('task-log-content-' + taskId);
    if (logContent) logContent.innerHTML = '';
}

function finalizeTaskLog(taskId, cancelled) {
    var logStatus = document.getElementById('task-log-status-' + taskId);
    if (logStatus) {
        logStatus.textContent = cancelled ? '⏹ 已停止' : '✅ 已完成';
        logStatus.style.color = cancelled ? 'var(--text-dim)' : 'var(--green)';
    }
}

// ==================== SSE 流式处理 ====================

async function startTaskStream(taskId, sessionId, initMessage, fileIds) {
    try {
        var response = await api.chatStreamUrl(initMessage, sessionId, fileIds.length > 0 ? fileIds : null);
        var reader = response.body.getReader();
        var decoder = new TextDecoder();
        var buffer = '';
        var hasResult = false;

        // 为这个 task 初始化文本缓冲
        _textBuffer[taskId] = { text: '' };

        while (true) {
            if (!_runningTasks[taskId] || _runningTasks[taskId].sessionId !== sessionId) break;

            var result = await reader.read();
            if (result.done) break;

            buffer += decoder.decode(result.value, { stream: true });
            var lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (var i = 0; i < lines.length; i++) {
                var line = lines[i].trim();
                if (!line || !line.startsWith('data: ')) continue;

                var jsonStr = line.slice(6).trim();
                if (jsonStr === '[DONE]') {
                    flushTextBuffer(taskId);
                    delete _runningTasks[taskId];
                    setRunButtonState(taskId, 'done');
                    finalizeTaskLog(taskId, false);
                    return;
                }

                try {
                    var evt = JSON.parse(jsonStr);
                    handleTaskStreamEvent(taskId, evt);
                } catch (e) { /* ignore parse errors */ }
            }
        }

        // 流结束（非 [DONE]）
        flushTextBuffer(taskId);
        delete _runningTasks[taskId];
        setRunButtonState(taskId, 'done');
        finalizeTaskLog(taskId, false);

    } catch (e) {
        flushTextBuffer(taskId);
        appendLogLine(taskId, 'error', '连接错误: ' + e.message);
        delete _runningTasks[taskId];
        setRunButtonState(taskId, 'done');
        finalizeTaskLog(taskId, false);
    }
}

function handleTaskStreamEvent(taskId, evt) {
    switch (evt.type) {

        case 'text_stream':
            // 缓冲文本而非立即显示，避免逐字拆分
            if (!_textBuffer[taskId]) _textBuffer[taskId] = { text: '' };
            _textBuffer[taskId].text += evt.delta;
            // 每隔一段时间通过非 text 事件 flush，这里不做 action
            break;

        case 'tool_stream_name':
            flushTextBuffer(taskId);
            appendLogLine(taskId, 'tool', '调用: ' + evt.name);
            break;

        case 'tool_call':
            flushTextBuffer(taskId);
            appendLogLine(taskId, 'tool', '执行: ' + evt.tool + ' [' + evt.step + ']');
            break;

        case 'tool_error':
            flushTextBuffer(taskId);
            appendLogLine(taskId, 'error', evt.error);
            break;

        case 'finish':
            flushTextBuffer(taskId);
            // ⭐ 输出结果时：清除之前所有日志，只保留结果
            clearLogContent(taskId);
            var reply = evt.reply || evt.summary || '任务完成';
            appendLogLine(taskId, 'result', reply);
            if (evt.tool_data) {
                appendLogLine(taskId, 'text', evt.tool_data.slice(0, 1000));
            }

            // 保存结果到后端
            var rt = _runningTasks[taskId];
            if (rt && rt.sessionId) {
                api.saveTaskRunResult(taskId, { session_id: rt.sessionId, result: reply }).catch(function() {});
            }
            break;

        case 'error':
            flushTextBuffer(taskId);
            appendLogLine(taskId, 'error', evt.message || '未知错误');
            break;

        case 'cancelled':
            flushTextBuffer(taskId);
            appendLogLine(taskId, 'system', '任务已取消');
            break;

        default:
            break;
    }
}

// ==================== 任务历史 ====================

function showTaskHistory(taskId, taskTitle) {
    api.getTaskRunResults(taskId).then(function(results) {
        var overlay = document.getElementById('modal-overlay');
        var content = document.getElementById('modal-content');

        var listHtml = '';
        if (!results || results.length === 0) {
            listHtml = '<p style="color:var(--text-dim);text-align:center;padding:40px 0;">暂无运行记录</p>';
        } else {
            listHtml = results.map(function(r) {
                var ts = r.timestamp || '';
                var resultText = r.result || '(空)';
                return '<div class="task-hist-item">'
                    +   '<div class="task-hist-time">' + escapeHtml(ts) + '</div>'
                    +   '<div class="task-hist-result">' + escapeHtml(resultText) + '</div>'
                    + '</div>';
            }).join('');
        }

        content.innerHTML = '<div style="display:flex;flex-direction:column;height:100%;">'
            +   '<h3 style="margin:0 0 12px 0;">📋 运行历史: ' + escapeHtml(taskTitle || '') + '</h3>'
            +   '<div style="flex:1;overflow-y:auto;padding-right:4px;">' + listHtml + '</div>'
            +   '<div class="modal-actions"><button class="btn" onclick="closeModal()">关闭</button></div>'
            + '</div>';
        overlay.classList.add('show');
    }).catch(function(e) {
        alert('加载历史失败: ' + e.message);
    });
}

// ==================== 缓存数据 ====================

async function loadTaskCache() {
    try {
        var [allTools, skills, mcps] = await Promise.all([
            api.getTools(),
            api.getSkills().catch(function() { return []; }),
            api.getMcpList().catch(function() { return []; }),
        ]);
        window.__taskCache = { allTools: allTools, skills: skills, mcps: mcps, _ready: true };
    } catch (e) {
        window.__taskCache = { allTools: [], skills: [], mcps: [], _ready: true };
    }
}

loadTaskCache();

// ── 暴露到全局 ──
window.showAddTaskModal = showAddTaskModal;
window.editTask = editTask;
window.deleteTaskConfirm = deleteTaskConfirm;
window.runTask = runTask;
window.showTaskHistory = showTaskHistory;
