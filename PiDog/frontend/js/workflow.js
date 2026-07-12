/* ============================================================
   workflow.js — AI 内容生成工作流（硅基流动 · 循环执行）
   完整模块化适配 PiDog 前端
   本质：可视化 DAG 节点编辑器 + API 调用执行引擎
   ============================================================ */

function renderWorkflowPage(container) {
    // ── DOM 辅助 ──
    function $(id) { return container.querySelector('#' + id); }

    // ── 常量 ──
    var API_BASE = 'https://api.siliconflow.cn/v1';
    var CACHE_KEY = 'sf_models_cache', CACHE_TIME_KEY = 'sf_models_cache_time', CACHE_DURATION = 10 * 60 * 1000, AUTO_SAVE_KEY = 'sf_workflow_autosave';

    // ── 状态 ──
    var nodes = [], connections = [], nodeIdCounter = 0, selectedNodeId = null;
    var dragState = { active: false, nodeId: null, offsetX: 0, offsetY: 0 };
    var connectDrag = { active: false, fromNodeId: null, fromPortId: null, fromPortType: null, currentX: 0, currentY: 0 };
    var isRunning = false, stopRequested = false, abortController = null, autoSaveEnabled = true, canvasPan = { x: 0, y: 0 }, canvasZoom = 1, fetchedModels = [];
    var apiKey = localStorage.getItem('sf_api_key') || '';
    var collapsedCats = {};

    // 多工作台
    var workspaces = [{ name: '工作流 1', nodes: [], connections: [], nodeIdCounter: 0, selectedNodeId: null, canvasPan: { x: 0, y: 0 }, canvasZoom: 1 }];
    var currentWs = 0;

    function saveCurrentWs() { var ws = workspaces[currentWs]; if (!ws) return; ws.nodes = nodes; ws.connections = connections; ws.nodeIdCounter = nodeIdCounter; ws.selectedNodeId = selectedNodeId; ws.canvasPan = { x: canvasPan.x, y: canvasPan.y }; ws.canvasZoom = canvasZoom; }

    function switchWorkspace(idx) {
        if (idx === currentWs || idx < 0 || idx >= workspaces.length) return;
        saveCurrentWs();
        currentWs = idx;
        var ws = workspaces[idx];
        nodes = ws.nodes;
        connections = ws.connections;
        nodeIdCounter = ws.nodeIdCounter;
        selectedNodeId = ws.selectedNodeId || null;
        canvasPan = ws.canvasPan || { x: 0, y: 0 };
        canvasZoom = ws.canvasZoom || 1;
        applyCanvasTransform();
        renderAll();
        renderTabBar();
        scheduleAutoSave();
    }

    function addWorkspace() {
        saveCurrentWs();
        var idx = workspaces.length;
        workspaces.push({ name: '工作流 ' + (idx + 1), nodes: [], connections: [], nodeIdCounter: 0, selectedNodeId: null, canvasPan: { x: 0, y: 0 }, canvasZoom: 1 });
        currentWs = idx;
        var ws = workspaces[idx];
        nodes = ws.nodes;
        connections = ws.connections;
        nodeIdCounter = ws.nodeIdCounter;
        selectedNodeId = null;
        canvasPan = { x: 0, y: 0 };
        canvasZoom = 1;
        applyCanvasTransform();
        renderAll();
        renderTabBar();
        showToast('已新建工作台', 'success');
    }

    function removeWorkspace(idx) {
        if (workspaces.length <= 1) { showToast('至少保留一个工作台', ''); return; }
        saveCurrentWs();
        workspaces.splice(idx, 1);
        if (currentWs >= workspaces.length) currentWs = workspaces.length - 1;
        var ws = workspaces[currentWs];
        nodes = ws.nodes;
        connections = ws.connections;
        nodeIdCounter = ws.nodeIdCounter;
        selectedNodeId = ws.selectedNodeId || null;
        canvasPan = ws.canvasPan || { x: 0, y: 0 };
        canvasZoom = ws.canvasZoom || 1;
        applyCanvasTransform();
        renderAll();
        renderTabBar();
        scheduleAutoSave();
    }

    var CATEGORIES = [
        { key: 'chat', icon: '💬', label: '对话模型' },
        { key: 'reasoning', icon: '🧠', label: '推理模型' },
        { key: 'image-gen', icon: '🎨', label: '生图模型' },
        { key: 'image-understand', icon: '👁️', label: '图片理解' },
        { key: 'vision', icon: '👀', label: '视觉模型' },
        { key: 'video-gen', icon: '🎬', label: '视频生成' },
        { key: 'video-understand', icon: '📹', label: '视频理解' },
        { key: 'tts', icon: '🔊', label: '语音合成(TTS)' },
        { key: 'asr', icon: '🎤', label: '语音识别(ASR)' },
    ];
    var CATEGORY_KEYS = CATEGORIES.map(function(c) { return c.key; });
    var TYPE_ICONS = {};
    CATEGORIES.forEach(function(c) { TYPE_ICONS[c.key] = c.icon; });
    var TYPE_LABELS = {};
    CATEGORIES.forEach(function(c) { TYPE_LABELS[c.key] = c.label; });
    var LOOP_LABELS = ['in', 'next', 'body', 'out'];

    // ── 构建界面 ──
    container.innerHTML =
        '<div class="workflow-page" style="height:100%;">' +
        '  <div class="wf-sidebar">' +
        '    <div class="wf-sidebar-header">✨ 硅基流动 · 模型广场</div>' +
        '    <div class="wf-api-section">' +
        '      <input type="password" id="wfApiKeyInput" placeholder="输入 SiliconFlow API Key ..." />' +
        '      <div class="wf-api-actions">' +
        '        <button id="wfLoadModelsBtn">🔄 加载模型广场</button>' +
        '        <button id="wfClearCacheBtn" style="background:#4a4a5a;flex:0.4">清空缓存</button>' +
        '      </div>' +
        '      <div class="wf-api-status" id="wfApiStatus">输入 API Key 后点击加载</div>' +
        '    </div>' +
        '    <div class="wf-mgmt">' +
        '      <div class="wf-title">📂 工作流管理</div>' +
        '      <div class="wf-row">' +
        '        <button id="wfSaveWfBtn">💾 保存到文件</button>' +
        '        <button id="wfLoadWfBtn">📂 加载工作流</button>' +
        '      </div>' +
        '      <div class="wf-row">' +
        '        <button id="wfAutoSaveToggle">⏸ 自动保存: 开</button>' +
        '      </div>' +
        '    </div>' +
        '    <div class="wf-category">📥 媒体输入</div>' +
        '    <button class="wf-media-btn" data-media="text"><span>📄</span> 文本输入</button>' +
        '    <button class="wf-media-btn" data-media="image"><span>🖼️</span> 图片输入</button>' +
        '    <button class="wf-media-btn" data-media="audio"><span>🎵</span> 音频输入</button>' +
        '    <button class="wf-media-btn" data-media="video"><span>🎬</span> 视频输入</button>' +
        '    <div class="wf-category">🔄 循环控制</div>' +
        '    <button class="wf-loop-btn" id="wfAddLoopStartBtn"><span>🔁</span> 循环开始</button>' +
        '    <button class="wf-loop-btn" id="wfAddLoopEndBtn"><span>⏹</span> 循环结束</button>' +
        '    <div class="wf-category">📊 数据流</div>' +
        '    <button class="wf-media-btn" id="wfAddMonitorBtn"><span>📊</span> 数据传输展示</button>' +
        '    <button class="wf-media-btn" id="wfAddExportBtn"><span>💾</span> 数据保存导出</button>' +
        '    <div class="wf-category" id="wfModelPlazaTitle">🤖 模型广场 <span class="wf-model-count" id="wfModelCount">(0)</span></div>' +
        '    <div style="padding:3px 10px 5px;">' +
        '      <input type="text" id="wfModelSearchInput" class="wf-model-search-input" placeholder="🔍 搜索模型名称 / 厂商 ..." />' +
        '    </div>' +
        '    <div id="wfDynamicModelsContainer"></div>' +
        '    <div class="wf-category">📤 最终输出</div>' +
        '    <button class="wf-output-btn" data-output="display"><span>🖥️</span> 输出内容展示</button>' +
        '    <button class="wf-output-btn" data-output="save"><span>💾</span> 保存到本地</button>' +
        '    <div class="wf-sidebar-footer">🖱 拖拽端口连线 · 连线可删除 · 循环: next→next 回传</div>' +
        '  </div>' +
        '  <div class="wf-workspace-area">' +
        '    <div class="wf-tab-bar" id="wfTabBar"></div>' +
        '    <div class="wf-canvas-container" id="wfCanvasContainer">' +
        '      <div class="wf-canvas-viewport" id="wfCanvasViewport">' +
        '        <div class="wf-nodes-layer" id="wfNodesLayer"></div>' +
        '        <svg class="wf-line-layer" id="wfLineLayer"></svg>' +
        '      </div>' +
        '      <div class="wf-canvas-zoom-info" id="wfZoomInfo">100%</div>' +
        '      <div class="wf-kb-hint"><kbd>Del</kbd> 删除 · <kbd>Ctrl+D</kbd> 复制 · <kbd>Ctrl+S</kbd> 保存 · 滚轮缩放</div>' +
        '      <div class="wf-floating-actions">' +
        '        <button class="wf-action-btn" id="wfClearAllBtn">🗑️ 清空</button>' +
        '        <button class="wf-action-btn" id="wfFitViewBtn">⊞ 适应</button>' +
        '        <button class="wf-action-btn primary" id="wfRunWorkflowBtn">▶️ 运行工作流</button>' +
        '      </div>' +
        '    </div>' +
        '  </div>' +
        '  <input type="file" id="wfFileInput" class="wf-wf-file-input" accept=".json" />' +
        '</div>';

    // ── Toast（固定在 body） ──
    var toastEl = document.getElementById('wf-toast-fixed');
    if (!toastEl) {
        toastEl = document.createElement('div');
        toastEl.id = 'wf-toast-fixed';
        toastEl.className = 'wf-toast-fixed';
        document.body.appendChild(toastEl);
    }

    // ── DOM 引用 ──
    var nodesLayer = $('wfNodesLayer');
    var canvasContainer = $('wfCanvasContainer');
    var canvasViewport = $('wfCanvasViewport');
    var lineLayer = $('wfLineLayer');
    var apiKeyInput = $('wfApiKeyInput');
    var loadModelsBtn = $('wfLoadModelsBtn');
    var clearCacheBtn = $('wfClearCacheBtn');
    var apiStatus = $('wfApiStatus');
    var dynamicContainer = $('wfDynamicModelsContainer');
    var zoomInfo = $('wfZoomInfo');
    var wfFileInput = $('wfFileInput');

    // ── 模型分类 ──
    function categorizeModelId(id) {
        var i = id.toLowerCase();
        if (/kling|cogvideo|videocrafter|modelscope.*t2v|text2video|t2v-|video-gen|wan.*video/.test(i)) return 'video-gen';
        if (/video-llama|videochat|valley|video-blip|internvideo|video-llava/.test(i)) return 'video-understand';
        if (/stable-diffusion|flux|sdxl|sd3|dall-e|playground|pixart|kolors|latent-consistency|wurstchen|deepfloyd|lumina|auraflow|sana/.test(i)) return 'image-gen';
        if (/vl\d?$|vision|internvl|cogvlm|deepseek-vl|qwen2?-vl|minicpmv|glm-4v|llava|yi-vl|openbmb.*vl|phi.*vision/.test(i)) return 'image-understand';
        if (/ocr|got-|image-to-text|img2txt|visual.*qa|visual.*ground|grounding|detection|segmentation|sam-|clip-|imagebind|image-editor|inpainting|outpainting/.test(i)) return 'vision';
        if (/cosyvoice|tts-?1|fishtalk|chattts|gptsovits|bark|vall-e/.test(i)) return 'tts';
        if (/whisper|sensevoice|parakeet|asr|speech.?recog|voice.?recog|transcri/.test(i)) return 'asr';
        if (/deepseek.*r1|qwq|reasoning|deep.*think|o1-|o3-/.test(i)) return 'reasoning';
        if (/embedding|rerank|bge|bce-embedding|gte|text2vec/.test(i)) return null;
        return 'chat';
    }

    function getShortName(m) { var p = m.split('/'); return p[p.length - 1]; }

    function getOwner(m) { var p = m.split('/'); return p.length > 1 ? p[0] : 'siliconflow'; }

    function getDefaultParams(type) {
        switch (type) {
            case 'chat': return { temperature: 0.7, max_tokens: 2048 };
            case 'reasoning': return { temperature: 0.6, max_tokens: 4096 };
            case 'image-gen': return { width: 1024, height: 1024, steps: 25, guidance_scale: 7.5 };
            case 'image-understand': return { max_tokens: 1024, temperature: 0.5 };
            case 'vision': return { max_tokens: 1024, temperature: 0.3 };
            case 'video-gen': return { width: 1280, height: 720, duration: 5 };
            case 'video-understand': return { max_tokens: 1024 };
            case 'tts': return { voice: 'default', speed: 1.0 };
            case 'asr': return { language: 'auto' };
            default: return {};
        }
    }

    function getPortsByType(type) {
        var P = {
            'chat': { i: ['text'], o: ['text'] },
            'reasoning': { i: ['text'], o: ['text'] },
            'image-gen': { i: ['text'], o: ['image'] },
            'image-understand': { i: ['image', 'text'], o: ['text'] },
            'vision': { i: ['image', 'text'], o: ['text'] },
            'video-gen': { i: ['text'], o: ['video'] },
            'video-understand': { i: ['video', 'text'], o: ['text'] },
            'tts': { i: ['text'], o: ['audio'] },
            'asr': { i: ['audio'], o: ['text'] },
            'loop-start': { i: ['in', 'next'], o: ['body'] },
            'loop-end': { i: ['body'], o: ['next', 'out'] },
            'data-monitor': { i: ['text', 'image', 'audio', 'video'], o: ['text', 'image', 'audio', 'video'] },
            'data-export': { i: ['text', 'image', 'audio', 'video'], o: ['text', 'image', 'audio', 'video'] },
            'media-text': { i: [], o: ['text'] },
            'media-image': { i: [], o: ['image'] },
            'media-audio': { i: [], o: ['audio'] },
            'media-video': { i: [], o: ['video'] },
            'output-display': { i: ['text', 'image', 'audio', 'video'], o: [] },
            'output-save': { i: ['text', 'image', 'audio', 'video'], o: [] },
        };
        var p = P[type] || { i: ['data'], o: ['data'] };
        return { inputs: p.i, outputs: p.o };
    }

    // ── API ──
    async function fetchModelsFromAPI(key) {
        var r = await fetch(API_BASE + '/models', { headers: { 'Authorization': 'Bearer ' + key } });
        if (!r.ok) { var m = 'HTTP ' + r.status; try { var e = await r.json(); m = e.message || e.error?.message || m } catch (_) {} throw new Error(m); }
        var d = await r.json(),
            raw = d.data || [];
        var cat = raw.map(function(m) {
            return { id: m.id, owned_by: m.owned_by || getOwner(m.id), capabilities: m.capabilities || {}, _category: categorizeModelId(m.id), _shortName: getShortName(m.id) };
        }).filter(function(m) { return m._category !== null && CATEGORY_KEYS.indexOf(m._category) >= 0; });
        try { localStorage.setItem(CACHE_KEY, JSON.stringify(cat));
            localStorage.setItem(CACHE_TIME_KEY, String(Date.now())) } catch (_) {}
        return cat;
    }

    function loadCachedModels() { try { var c = localStorage.getItem(CACHE_KEY),
                t = localStorage.getItem(CACHE_TIME_KEY); if (c && t && (Date.now() - Number(t)) < CACHE_DURATION) return JSON.parse(c) } catch (_) {} return null; }

    // ── 画布变换 ──
    function applyCanvasTransform() {
        canvasViewport.style.transform = 'translate(' + canvasPan.x + 'px,' + canvasPan.y + 'px) scale(' + canvasZoom + ')';
        zoomInfo.textContent = Math.round(canvasZoom * 100) + '%';
    }

    function zoomCanvas(f, cx, cy) {
        var old = canvasZoom;
        canvasZoom = Math.min(3, Math.max(0.15, canvasZoom * f));
        var r = canvasContainer.getBoundingClientRect();
        var mx = cx !== undefined ? cx - r.left : r.width / 2,
            my = cy !== undefined ? cy - r.top : r.height / 2;
        canvasPan.x = mx - (mx - canvasPan.x) * (canvasZoom / old);
        canvasPan.y = my - (my - canvasPan.y) * (canvasZoom / old);
        applyCanvasTransform();
    }

    function fitView() {
        if (!nodes.length) { canvasPan = { x: 0, y: 0 };
            canvasZoom = 1;
            applyCanvasTransform(); return; }
        var minX = Infinity,
            minY = Infinity,
            maxX = -Infinity,
            maxY = -Infinity;
        nodes.forEach(function(n) {
            if (n.x < minX) minX = n.x;
            if (n.y < minY) minY = n.y;
            if (n.x + 280 > maxX) maxX = n.x + 280;
            if (n.y + 220 > maxY) maxY = n.y + 220;
        });
        var r = canvasContainer.getBoundingClientRect(),
            z = Math.min(r.width / (maxX - minX + 120), r.height / (maxY - minY + 120), 1.5);
        canvasZoom = z;
        canvasPan.x = r.width / 2 - (minX + maxX) / 2 * z;
        canvasPan.y = r.height / 2 - (minY + maxY) / 2 * z;
        applyCanvasTransform();
    }

    // ── 节点创建 ──
    function createNode(type, modelIdOrData, x, y) {
        var id = 'node_' + (++nodeIdCounter);
        var nodeData = { id: id, x: x, y: y, systemPrompt: '' };
        if (type.indexOf('media-') === 0) {
            var mt = type.replace('media-', '');
            nodeData.type = type;
            nodeData.mediaType = mt;
            nodeData.modelName = mt === 'text' ? '📝 文本输入' : mt.toUpperCase() + ' 输入';
            nodeData.fileData = null;
            nodeData.textContent = '';
        } else if (type === 'loop-start') {
            nodeData.type = type;
            nodeData.modelName = '🔁 循环开始';
            nodeData.params = { max_iterations: 10, current_iteration: 0 };
        } else if (type === 'loop-end') {
            nodeData.type = type;
            nodeData.modelName = '⏹ 循环结束';
        } else if (type === 'data-export') {
            nodeData.type = type;
            nodeData.modelName = '💾 数据保存';
            nodeData.saveFolder = 'my_data';
            nodeData.savedContent = null;
            nodeData.savedContentType = null;
        } else if (type === 'data-monitor') {
            nodeData.type = type;
            nodeData.modelName = '📊 数据传输展示';
            nodeData.savedContent = null;
            nodeData.savedContentType = null;
        } else if (type.indexOf('output-') === 0) {
            var ot = type.replace('output-', '');
            nodeData.type = type;
            nodeData.modelName = ot === 'display' ? '📺 内容展示' : '💾 保存到本地';
            nodeData.savedContent = null;
            if (ot === 'save') nodeData.downloadPath = 'output.txt';
        } else if (typeof modelIdOrData === 'object' && modelIdOrData !== null) {
            nodeData.modelId = modelIdOrData.id;
            nodeData.modelName = modelIdOrData._shortName;
            nodeData.owned_by = modelIdOrData.owned_by;
            nodeData.type = modelIdOrData._category;
            nodeData.params = JSON.parse(JSON.stringify(getDefaultParams(modelIdOrData._category)));
        } else return null;
        var ports = getPortsByType(nodeData.type);
        nodeData.inputs = ports.inputs.map(function(l, i) { return { id: id + '_in_' + i, label: l }; });
        nodeData.outputs = ports.outputs.map(function(l, i) { return { id: id + '_out_' + i, label: l }; });
        return nodeData;
    }

    // ── 渲染 ──
    function renderAll() { renderNodes();
        renderLines(); }

    function renderNodes() {
        nodesLayer.innerHTML = '';
        nodes.forEach(function(node) {
            var card = document.createElement('div');
            card.className = 'wf-node-card' + (selectedNodeId === node.id ? ' selected' : '');
            card.dataset.nodeId = node.id;
            card.dataset.type = node.type;
            card.style.left = node.x + 'px';
            card.style.top = node.y + 'px';
            var icon = TYPE_ICONS[node.type] || '🔹';
            var header = document.createElement('div');
            header.className = 'wf-node-header';
            header.innerHTML = '<span>' + icon + ' ' + escapeHtml(node.modelName || node.type) + (node.owned_by ? '<span class="wf-node-type-badge">' + escapeHtml(node.owned_by) + '</span>' : '') + '</span><button class="wf-delete-node" data-delete="' + node.id + '">✕</button>';
            var body = document.createElement('div');
            body.className = 'wf-node-body';
            if (node.type === 'media-text') body.innerHTML = buildMediaTextBody(node);
            else if (node.type.indexOf('media-') === 0) body.innerHTML = buildMediaFileBody(node);
            else if (node.type === 'loop-start') body.innerHTML = buildLoopStartBody(node);
            else if (node.type === 'loop-end') body.innerHTML = buildLoopEndBody(node);
            else if (node.type === 'data-export') body.innerHTML = buildDataExportBody(node);
            else if (node.type === 'data-monitor') body.innerHTML = buildDataMonitorBody(node);
            else if (node.type === 'output-display') body.innerHTML = buildOutputDisplayBody(node);
            else if (node.type === 'output-save') body.innerHTML = buildOutputSaveBody(node);
            else body.innerHTML = buildModelBody(node);

            var ioDiv = document.createElement('div');
            ioDiv.className = 'wf-io-ports';
            var inDiv = document.createElement('div');
            inDiv.className = 'wf-port-group';
            node.inputs.forEach(function(p) {
                var isLoop = LOOP_LABELS.indexOf(p.label) >= 0;
                inDiv.innerHTML += '<div class="wf-port wf-input-port' + (isLoop ? ' wf-loop-port' : '') + '" data-port-id="' + p.id + '" data-node="' + node.id + '"><span class="wf-port-dot"></span> ' + p.label + '</div>';
            });
            var outDiv = document.createElement('div');
            outDiv.className = 'wf-port-group wf-output-port';
            node.outputs.forEach(function(p) {
                var isLoop = LOOP_LABELS.indexOf(p.label) >= 0;
                outDiv.innerHTML += '<div class="wf-port' + (isLoop ? ' wf-loop-port' : '') + '" data-port-id="' + p.id + '" data-node="' + node.id + '">' + p.label + ' <span class="wf-port-dot"></span></div>';
            });
            ioDiv.appendChild(inDiv);
            ioDiv.appendChild(outDiv);
            body.appendChild(ioDiv);
            card.appendChild(header);
            card.appendChild(body);
            header.addEventListener('mousedown', function(e) { onDragStart(e, node.id); });
            card.addEventListener('click', function(e) {
                if (e.target.classList.contains('wf-delete-node') || e.target.closest('.wf-port') || e.target.closest('input') || e.target.closest('textarea')) return;
                selectNode(node.id);
            });
            nodesLayer.appendChild(card);
        });
        container.querySelectorAll('.wf-delete-node').forEach(function(b) {
            b.addEventListener('click', function(e) { e.stopPropagation();
                deleteNode(b.dataset.delete); });
        });
        container.querySelectorAll('input[data-param]').forEach(function(inp) {
            inp.addEventListener('input', function() {
                var n = nodes.find(function(x) { return x.id === inp.dataset.node; });
                if (!n) return;
                if (inp.dataset.param === 'filename') n.downloadPath = inp.value;
                else if (inp.dataset.param === 'saveFolder') n.saveFolder = inp.value;
                else if (n.params && n.params.hasOwnProperty(inp.dataset.param)) {
                    var v = inp.value;
                    if (!isNaN(v) && v.trim() !== '') v = parseFloat(v);
                    n.params[inp.dataset.param] = v;
                }
                scheduleAutoSave();
            });
        });
        container.querySelectorAll('.wf-system-prompt').forEach(function(ta) {
            ta.addEventListener('input', function() {
                var n = nodes.find(function(x) { return x.id === ta.dataset.node; });
                if (n) { n.systemPrompt = ta.value;
                    scheduleAutoSave(); }
            });
        });
        container.querySelectorAll('.wf-inline-text').forEach(function(ta) {
            ta.addEventListener('input', function() {
                var n = nodes.find(function(x) { return x.id === ta.dataset.node; });
                if (n) { n.textContent = ta.value;
                    scheduleAutoSave(); }
            });
        });
        container.querySelectorAll('.wf-file-input').forEach(function(inp) {
            inp.addEventListener('change', function() {
                var n = nodes.find(function(x) { return x.id === inp.dataset.node; });
                if (n && inp.files[0]) n.fileData = inp.files[0];
            });
        });
        container.querySelectorAll('.wf-dir-pick-btn').forEach(function(btn) {
            btn.addEventListener('click', function(e) { e.stopPropagation();
                pickDirectory(btn.dataset.node); });
        });
        // 端口连线
        container.querySelectorAll('.wf-port').forEach(function(el) {
            var start = function(e) {
                if (e.button !== 0) return;
                e.preventDefault();
                connectDrag.active = true;
                connectDrag.fromNodeId = el.dataset.node;
                connectDrag.fromPortId = el.dataset.portId;
                connectDrag.fromPortType = el.parentElement.classList.contains('wf-output-port') ? 'output' : 'input';
                var r = canvasContainer.getBoundingClientRect();
                connectDrag.currentX = (e.clientX - r.left - canvasPan.x) / canvasZoom;
                connectDrag.currentY = (e.clientY - r.top - canvasPan.y) / canvasZoom;
                window.addEventListener('mousemove', onConnectMove);
                window.addEventListener('mouseup', onConnectEnd);
                renderLines();
            };
            el.addEventListener('mousedown', start);
        });
    }

    function buildMediaTextBody(n) {
        return '<div class="wf-param-row"><label>📝 输入文本内容</label><textarea class="wf-inline-text" data-node="' + n.id + '" placeholder="在此输入文本 ...">' + escapeHtml(n.textContent || '') + '</textarea></div>';
    }

    function buildMediaFileBody(n) {
        var a = { image: 'image/*', audio: 'audio/*', video: 'video/*' };
        return '<div class="wf-param-row"><label>📎 上传' + n.mediaType.toUpperCase() + '文件</label><input type="file" accept="' + (a[n.mediaType] || '*') + '" data-node="' + n.id + '" class="wf-file-input" /></div>';
    }

    function buildOutputDisplayBody(n) {
        var c = n.savedContent || '等待输入...';
        var isImg = n.savedContentType === 'image' && n.savedContent;
        var inner = isImg ? '<img src="' + n.savedContent + '" alt="输出" />' : (typeof c === 'string' ? escapeHtml(c) : escapeHtml(JSON.stringify(c, null, 2)));
        return '<div class="wf-param-row"><label>📺 接收内容预览</label><div class="wf-output-display" data-node="' + n.id + '">' + inner + '</div></div>';
    }

    function buildOutputSaveBody(n) {
        var dirName = n.directoryHandle?.name || n._dirName || '未选择';
        var fname = n.downloadPath || 'output.txt';
        return '<div class="wf-param-row"><label>📁 保存目录</label><div style="display:flex;gap:4px;"><span style="flex:1;background:#1e1e26;border:1px solid #4a4a56;color:white;padding:5px 8px;border-radius:5px;font-size:12px;overflow:hidden;text-overflow:ellipsis;">' + escapeHtml(dirName) + '</span><button class="wf-dir-pick-btn" data-node="' + n.id + '">📂 选择</button></div></div><div class="wf-param-row"><label>💾 文件名（留空自动生成）</label><input type="text" value="' + escapeHtml(fname) + '" placeholder="留空自动生成" data-param="filename" data-node="' + n.id + '"/></div>';
    }

    function buildDataMonitorBody(n) {
        var c = n.savedContent || '等待数据...';
        var isImg = n.savedContentType === 'image' && n.savedContent;
        var inner = isImg ? '<img src="' + n.savedContent + '" alt="数据" />' : (typeof c === 'string' ? escapeHtml(c) : escapeHtml(JSON.stringify(c, null, 2)));
        return '<div class="wf-param-row"><label>📊 流经数据预览</label><div class="wf-output-display" style="border-color:#6a4a6a;" data-node="' + n.id + '">' + inner + '</div></div>';
    }

    function buildDataExportBody(n) {
        var c = n.savedContent || '等待数据...';
        var dirName = n.directoryHandle?.name || n._dirName || '未选择';
        var fname = n.downloadPath || '';
        var isImg = n.savedContentType === 'image' && n.savedContent;
        var inner = isImg ? '<img src="' + n.savedContent + '" alt="数据" />' : (typeof c === 'string' ? escapeHtml(c) : escapeHtml(JSON.stringify(c, null, 2)));
        return '<div class="wf-param-row"><label>📁 保存目录</label><div style="display:flex;gap:4px;"><span style="flex:1;background:#1e1e26;border:1px solid #4a4a56;color:white;padding:5px 8px;border-radius:5px;font-size:12px;overflow:hidden;text-overflow:ellipsis;">' + escapeHtml(dirName) + '</span><button class="wf-dir-pick-btn" data-node="' + n.id + '">📂 选择</button></div></div><div class="wf-param-row"><label>💾 文件名（留空自动生成）</label><input type="text" value="' + escapeHtml(fname) + '" placeholder="留空自动生成" data-param="filename" data-node="' + n.id + '"/></div><div class="wf-param-row"><label>💾 最后保存内容</label><div class="wf-output-display" style="border-color:#3a5a4a;" data-node="' + n.id + '">' + inner + '</div></div>';
    }

    function buildModelBody(n) {
        var h = '<div class="wf-param-row"><label>📝 系统提示词</label><textarea class="wf-system-prompt" data-node="' + n.id + '" placeholder="你是一个有帮助的 AI 助手 ...">' + escapeHtml(n.systemPrompt || '') + '</textarea></div>';
        if (n.params) {
            for (var k in n.params) {
                if (n.params.hasOwnProperty(k)) {
                    h += '<div class="wf-param-row"><label>' + k + '</label><input type="text" value="' + escapeHtml(String(n.params[k])) + '" data-param="' + k + '" data-node="' + n.id + '"/></div>';
                }
            }
        }
        if (n.modelId) h += '<div class="wf-param-row"><label>模型</label><span style="color:#aaa;font-size:10px;word-break:break-all;">' + escapeHtml(n.modelId) + '</span></div>';
        return h;
    }

    function buildLoopStartBody(n) {
        var iter = n.params?.current_iteration || 0,
            mx = n.params?.max_iterations || 10;
        return '<div class="wf-param-row"><label>🔄 循环迭代 <span class="wf-iter-badge">' + iter + '/' + mx + '</span></label></div><div class="wf-param-row"><label>max_iterations</label><input type="text" value="' + mx + '" data-param="max_iterations" data-node="' + n.id + '"/></div>';
    }

    function buildLoopEndBody(n) {
        return '<div class="wf-param-row"><label>⏹ 循环结束节点</label><span style="color:#aaa;font-size:11px;">next→回传 · out→退出</span></div>';
    }

    function renderLines() {
        var svg = '';
        var cR = canvasContainer.getBoundingClientRect();
        connections.forEach(function(conn, i) {
            var fE = container.querySelector('.wf-port[data-port-id="' + conn.fromPortId + '"]');
            var tE = container.querySelector('.wf-port[data-port-id="' + conn.toPortId + '"]');
            if (!fE || !tE) return;
            var fR = fE.getBoundingClientRect(),
                tR = tE.getBoundingClientRect();
            var x1 = (fR.left + fR.width / 2 - cR.left - canvasPan.x) / canvasZoom,
                y1 = (fR.top + fR.height / 2 - cR.top - canvasPan.y) / canvasZoom;
            var x2 = (tR.left + tR.width / 2 - cR.left - canvasPan.x) / canvasZoom,
                y2 = (tR.top + tR.height / 2 - cR.top - canvasPan.y) / canvasZoom;
            var dx = Math.abs(x2 - x1),
                cp = Math.max(dx * 0.45, 50);
            var isLoopBack = conn.fromLabel === 'next' || conn.toLabel === 'next';
            svg += '<path class="wf-conn-line' + (isLoopBack ? ' wf-loop-back' : '') + '" data-conn-idx="' + i + '" d="M' + x1 + ',' + y1 + ' C' + (x1 + cp) + ',' + y1 + ' ' + (x2 - cp) + ',' + y2 + ' ' + x2 + ',' + y2 + '" />';
        });
        if (connectDrag.active) {
            var fE = container.querySelector('.wf-port[data-port-id="' + connectDrag.fromPortId + '"]');
            if (fE) {
                var fR = fE.getBoundingClientRect();
                var x1 = (fR.left + fR.width / 2 - cR.left - canvasPan.x) / canvasZoom,
                    y1 = (fR.top + fR.height / 2 - cR.top - canvasPan.y) / canvasZoom;
                var dx = Math.abs(x1 - connectDrag.currentX),
                    cp = Math.max(dx * 0.45, 50);
                svg += '<path d="M' + x1 + ',' + y1 + ' C' + (x1 + cp) + ',' + y1 + ' ' + (connectDrag.currentX - cp) + ',' + connectDrag.currentY + ' ' + connectDrag.currentX + ',' + connectDrag.currentY + '" stroke-dasharray="6,4" stroke="#aaa" />';
            }
        }
        lineLayer.innerHTML = svg;
    }

    // ── 侧边栏 ──
    function getSearchQuery() { var el = $('wfModelSearchInput'); return el ? el.value.trim().toLowerCase() : ''; }

    function toggleCategory(key) { collapsedCats[key] = !collapsedCats[key];
        renderSidebarModels(); }

    function renderSidebarModels() {
        var mcEl = $('wfModelCount');
        if (!fetchedModels.length) { dynamicContainer.innerHTML = '<div class="wf-no-models" style="padding:10px 14px;">点击上方「加载模型广场」获取模型</div>'; if (mcEl) mcEl.textContent = '(0)'; return; }
        var q = getSearchQuery(),
            isSearching = !!q;
        var html = '',
            total = 0;
        for (var ci = 0; ci < CATEGORIES.length; ci++) {
            var cat = CATEGORIES[ci];
            var mds = fetchedModels.filter(function(m) { return m._category === cat.key; });
            if (!mds.length) continue;
            if (q) mds = mds.filter(function(m) { return m._shortName.toLowerCase().indexOf(q) >= 0 || m.id.toLowerCase().indexOf(q) >= 0 || (m.owned_by && m.owned_by.toLowerCase().indexOf(q) >= 0); });
            if (!mds.length) continue;
            total += mds.length;
            var open = isSearching || collapsedCats[cat.key] !== false;
            html += '<div class="wf-category" data-cat-key="' + cat.key + '"><span class="wf-cat-toggle ' + (open ? 'open' : '') + '">▶</span> ' + cat.icon + ' ' + cat.label + ' <span class="wf-model-count">(' + mds.length + ')</span></div><div class="wf-dynamic-models-scroll ' + (open ? '' : 'collapsed') + '">';
            for (var mi = 0; mi < mds.length; mi++) {
                var m = mds[mi];
                html += '<button class="wf-model-btn" data-model-id="' + escapeHtml(m.id) + '"><span class="wf-model-icon">' + cat.icon + '</span><span class="wf-model-info"><span class="wf-model-name">' + escapeHtml(m._shortName) + '</span><span class="wf-model-provider">' + escapeHtml(m.owned_by || '') + '</span></span></button>';
            }
            html += '</div>';
        }
        if (!html) html = '<div class="wf-no-models" style="padding:10px 14px;">没有匹配「' + escapeHtml(q) + '」的模型</div>';
        dynamicContainer.innerHTML = html;
        if (mcEl) mcEl.textContent = '(' + total + ')';
        dynamicContainer.querySelectorAll('.wf-category').forEach(function(el) {
            el.addEventListener('click', function() { var k = el.dataset.catKey; if (k) toggleCategory(k); });
        });
        dynamicContainer.querySelectorAll('.wf-model-btn').forEach(function(btn) {
            btn.addEventListener('click', function(e) { e.stopPropagation(); var m = fetchedModels.find(function(x) { return x.id === btn.dataset.modelId; }); if (m) addModelNode(m); });
        });
    }

    // ── 节点操作 ──
    function selectNode(id) { selectedNodeId = id;
        renderAll(); }

    function deleteNode(id) {
        nodes = nodes.filter(function(n) { return n.id !== id; });
        connections = connections.filter(function(c) { return c.fromNodeId !== id && c.toNodeId !== id; });
        if (selectedNodeId === id) selectedNodeId = null;
        renderAll();
        scheduleAutoSave();
    }

    function duplicateNode(nid) {
        var src = nodes.find(function(n) { return n.id === nid; });
        if (!src) return;
        var n = JSON.parse(JSON.stringify(src));
        n.id = 'node_' + (++nodeIdCounter);
        n.x += 40;
        n.y += 40;
        n.inputs.forEach(function(p) { p.id = p.id.replace(/node_\d+/, n.id); });
        n.outputs.forEach(function(p) { p.id = p.id.replace(/node_\d+/, n.id); });
        n.fileData = null;
        n.savedContent = null;
        nodes.push(n);
        selectedNodeId = n.id;
        renderAll();
        showToast('节点已复制', 'success');
    }

    function addMediaNode(mt) { var n = createNode('media-' + mt, null, 60 + Math.random() * 180, 40 + Math.random() * 160); if (n) { nodes.push(n);
            renderAll(); } }

    function addModelNode(md) { var n = createNode(md._category, md, 180 + Math.random() * 220, 100 + Math.random() * 180); if (n) { nodes.push(n);
            renderAll(); } }

    function addOutputNode(ot) { var n = createNode('output-' + ot, null, 480 + Math.random() * 140, 320 + Math.random() * 100); if (n) { nodes.push(n);
            renderAll(); } }

    function addMonitorNode() { var n = createNode('data-monitor', null, 300 + Math.random() * 160, 240 + Math.random() * 120); if (n) { nodes.push(n);
            renderAll(); } }

    function addExportNode() { var n = createNode('data-export', null, 300 + Math.random() * 160, 240 + Math.random() * 120); if (n) { nodes.push(n);
            renderAll(); } }

    function addLoopStartNode() { var n = createNode('loop-start', null, 200 + Math.random() * 120, 100 + Math.random() * 100); if (n) { nodes.push(n);
            renderAll(); } }

    function addLoopEndNode() { var n = createNode('loop-end', null, 400 + Math.random() * 120, 300 + Math.random() * 100); if (n) { nodes.push(n);
            renderAll(); } }

    async function pickDirectory(nodeId) {
        var n = nodes.find(function(x) { return x.id === nodeId; });
        if (!n) return;
        try {
            var h = await window.showDirectoryPicker();
            n.directoryHandle = h;
            n._dirName = h.name;
            showToast('已选择目录: ' + h.name, 'success');
            renderAll();
            scheduleAutoSave();
        } catch (err) {
            if (err.name === 'AbortError') return;
            showToast('目录选择失败: ' + err.message + '; 使用文件夹名模式', 'error');
            n._dirName = n.saveFolder || 'export';
            renderAll();
        }
    }

    // ── 拖拽 & 连线 ──
    function onDragStart(e, nid) {
        if (e.button !== 0) return;
        e.preventDefault();
        var n = nodes.find(function(x) { return x.id === nid; });
        if (!n) return;
        var r = canvasContainer.getBoundingClientRect();
        dragState = { active: true, nodeId: nid, offsetX: e.clientX - r.left - n.x * canvasZoom - canvasPan.x, offsetY: e.clientY - r.top - n.y * canvasZoom - canvasPan.y };
        window.addEventListener('mousemove', onDragMove);
        window.addEventListener('mouseup', onDragEnd);
    }

    function onDragMove(e) {
        if (!dragState.active) return;
        var r = canvasContainer.getBoundingClientRect();
        var n = nodes.find(function(x) { return x.id === dragState.nodeId; });
        if (n) {
            n.x = (e.clientX - r.left - dragState.offsetX - canvasPan.x) / canvasZoom;
            n.y = (e.clientY - r.top - dragState.offsetY - canvasPan.y) / canvasZoom;
            renderAll();
        }
    }

    function onDragEnd() { dragState.active = false;
        window.removeEventListener('mousemove', onDragMove);
        window.removeEventListener('mouseup', onDragEnd);
        scheduleAutoSave(); }

    function onConnectMove(e) {
        if (!connectDrag.active) return;
        var r = canvasContainer.getBoundingClientRect();
        connectDrag.currentX = (e.clientX - r.left - canvasPan.x) / canvasZoom;
        connectDrag.currentY = (e.clientY - r.top - canvasPan.y) / canvasZoom;
        renderLines();
    }

    function onConnectEnd(e) {
        if (!connectDrag.active) return;
        var t = document.elementFromPoint(e.clientX, e.clientY);
        if (t && t.classList.contains('wf-port')) {
            var tn = t.dataset.node,
                tp = t.dataset.portId,
                isOut = t.parentElement.classList.contains('wf-output-port'),
                tt = isOut ? 'output' : 'input';
            if (connectDrag.fromNodeId !== tn && connectDrag.fromPortType !== tt) {
                var fn = nodes.find(function(x) { return x.id === connectDrag.fromNodeId; }),
                    tn2 = nodes.find(function(x) { return x.id === tn; });
                if (fn && tn2) {
                    var fp = fn[connectDrag.fromPortType === 'output' ? 'outputs' : 'inputs'].find(function(x) { return x.id === connectDrag.fromPortId; });
                    var tp2 = tn2[tt === 'input' ? 'inputs' : 'outputs'].find(function(x) { return x.id === tp; });
                    if (fp && tp2) {
                        var canConnect = fp.label === tp2.label || LOOP_LABELS.indexOf(fp.label) >= 0 || LOOP_LABELS.indexOf(tp2.label) >= 0;
                        if (canConnect) {
                            var si = connectDrag.fromPortType === 'output' ? connectDrag.fromNodeId : tn;
                            var sp = connectDrag.fromPortType === 'output' ? connectDrag.fromPortId : tp;
                            var di = connectDrag.fromPortType === 'output' ? tn : connectDrag.fromNodeId;
                            var dp = connectDrag.fromPortType === 'output' ? tp : connectDrag.fromPortId;
                            if (!connections.some(function(c) { return c.fromNodeId === si && c.fromPortId === sp && c.toNodeId === di && c.toPortId === dp; })) {
                                connections.push({ fromNodeId: si, fromPortId: sp, toNodeId: di, toPortId: dp, fromLabel: fp.label, toLabel: tp2.label });
                                scheduleAutoSave();
                            }
                        }
                    }
                }
            }
        }
        connectDrag.active = false;
        window.removeEventListener('mousemove', onConnectMove);
        window.removeEventListener('mouseup', onConnectEnd);
        renderAll();
    }

    // ── 工作流执行（含循环） ──
    function getInputDataForNode(node, results) {
        var inConns = connections.filter(function(c) { return c.toNodeId === node.id; }),
            data = {};
        for (var ci = 0; ci < inConns.length; ci++) {
            var c = inConns[ci];
            var fn = nodes.find(function(n) { return n.id === c.fromNodeId; });
            if (!fn) continue;
            var fp = fn.outputs.find(function(p) { return p.id === c.fromPortId; });
            if (!fp) continue;
            var r = results[fn.id];
            if (r !== undefined) {
                data[fp.label] = r;
                if (LOOP_LABELS.indexOf(fp.label) >= 0 && typeof r === 'string') data['text'] = r;
            }
        }
        return data;
    }

    async function executeNode(node, results, key, signal) {
        var inp = getInputDataForNode(node, results);
        if (node.type.indexOf('media-') === 0) {
            if (node.type === 'media-text') return node.textContent || '（空文本）';
            if (node.fileData) {
                if (node.mediaType === 'text') return await node.fileData.text();
                return await new Promise(function(res, rej) {
                    var r = new FileReader();
                    r.onload = function() { res(r.result); };
                    r.onerror = rej;
                    if (node.mediaType === 'image') r.readAsDataURL(node.fileData);
                    else r.readAsArrayBuffer(node.fileData);
                });
            }
            return node.mediaType === 'text' ? '（空文本）' : null;
        }
        if (node.type === 'loop-start') { return inp.in || inp.next || inp.text || inp.image || inp.audio || inp.video || null; }
        if (node.type === 'loop-end') { return inp.body || inp.text || inp.image || inp.audio || inp.video || null; }
        if (node.type === 'data-export') {
            var dt = inp.text !== undefined ? 'text' : inp.image !== undefined ? 'image' : inp.audio !== undefined ? 'audio' : inp.video !== undefined ? 'video' : null;
            var val = dt ? inp[dt] : null;
            if (val !== null && val !== undefined) {
                node.savedContent = val;
                node.savedContentType = dt;
                saveDataExport(node, dt, val);
            }
            return val;
        }
        if (node.type === 'data-monitor') {
            var dt = inp.text !== undefined ? 'text' : inp.image !== undefined ? 'image' : inp.audio !== undefined ? 'audio' : inp.video !== undefined ? 'video' : null;
            var c = dt ? inp[dt] : null;
            node.savedContent = c;
            node.savedContentType = dt;
            return c;
        }
        if (node.type === 'output-display') { node.savedContent = inp.text || inp.image || inp.audio || inp.video || '(无数据)';
            node.savedContentType = inp.image ? 'image' : 'text'; return node.savedContent; }
        if (node.type === 'output-save') {
            var c = inp.text || inp.image || inp.audio || inp.video || '(无数据)';
            saveOutputToFile(node, inp, c);
            return c;
        }
        var userText = inp.text || '',
            userImage = inp.image || null,
            userAudio = inp.audio || null;
        switch (node.type) {
            case 'chat':
            case 'reasoning':
                {
                    var msgs = [];
                    if (node.systemPrompt) msgs.push({ role: 'system', content: node.systemPrompt });
                    msgs.push({ role: 'user', content: userText || '你好' });
                    var b = { model: node.modelId, messages: msgs, temperature: node.params?.temperature ?? 0.7, max_tokens: node.params?.max_tokens ?? 2048, stream: false };
                    var r = await fetch(API_BASE + '/chat/completions', { signal: signal, method: 'POST', headers: { 'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json' }, body: JSON.stringify(b) });
                    if (!r.ok) { var m = 'HTTP ' + r.status; try { var e = await r.json();
                            m = e.message || e.error?.message || m } catch (_) {} throw new Error((TYPE_LABELS[node.type] || node.type) + ' ' + node.modelName + ': ' + m); }
                    var j = await r.json();
                    return j.choices?.[0]?.message?.content || '(无回复)';
                }
            case 'image-gen':
                {
                    var prompt = userText || (node.systemPrompt || '一幅美丽的风景画');
                    var b = { model: node.modelId, prompt: prompt, n: 1, size: (node.params?.width || 1024) + 'x' + (node.params?.height || 1024) };
                    var r = await fetch(API_BASE + '/image/generations', { signal: signal, method: 'POST', headers: { 'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json' }, body: JSON.stringify(b) });
                    if (!r.ok) { var m = 'HTTP ' + r.status; try { var e = await r.json();
                            m = e.message || e.error?.message || m } catch (_) {} throw new Error('生图模型 ' + node.modelName + ': ' + m); }
                    var j = await r.json();
                    var u = j.data?.[0]?.url || j.data?.[0]?.b64_json || '';
                    return (u && u.indexOf('http') !== 0 && u.indexOf('data:') !== 0) ? 'data:image/png;base64,' + u : u;
                }
            case 'image-understand':
            case 'vision':
                {
                    var msgs = [];
                    if (node.systemPrompt) msgs.push({ role: 'system', content: node.systemPrompt });
                    var content = [];
                    if (userImage) content.push({ type: 'image_url', image_url: { url: userImage } });
                    var promptText = node.type === 'vision' ? '请分析这张图片' : '请描述这张图片';
                    content.push({ type: 'text', text: userText || promptText });
                    msgs.push({ role: 'user', content: content });
                    var b = { model: node.modelId, messages: msgs, max_tokens: node.params?.max_tokens ?? 1024, temperature: node.params?.temperature ?? 0.5, stream: false };
                    var r = await fetch(API_BASE + '/chat/completions', { signal: signal, method: 'POST', headers: { 'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json' }, body: JSON.stringify(b) });
                    if (!r.ok) { var m = 'HTTP ' + r.status; try { var e = await r.json();
                            m = e.message || e.error?.message || m } catch (_) {} throw new Error('图片理解 ' + node.modelName + ': ' + m); }
                    var j = await r.json();
                    return j.choices?.[0]?.message?.content || '(无回复)';
                }
            case 'video-gen':
                throw new Error('视频生成暂未开放 API 调用');
            case 'video-understand':
                throw new Error('视频理解暂未开放 API 调用');
            case 'tts':
                {
                    var text = userText || (node.systemPrompt || '你好');
                    var b = { model: node.modelId, input: text, voice: node.params?.voice || 'default', speed: node.params?.speed || 1.0 };
                    var r = await fetch(API_BASE + '/audio/speech', { signal: signal, method: 'POST', headers: { 'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json' }, body: JSON.stringify(b) });
                    if (!r.ok) { var m = 'HTTP ' + r.status; try { var e = await r.json();
                            m = e.message || e.error?.message || m } catch (_) {} throw new Error('TTS ' + node.modelName + ': ' + m); }
                    var buf = await r.arrayBuffer();
                    return URL.createObjectURL(new Blob([buf], { type: 'audio/mpeg' }));
                }
            case 'asr':
                {
                    if (!userAudio) throw new Error('请连接音频输入节点');
                    var f = new FormData();
                    f.append('model', node.modelId);
                    f.append('language', node.params?.language || 'auto');
                    if (userAudio instanceof File) f.append('file', userAudio);
                    else if (typeof userAudio === 'string' && userAudio.indexOf('blob:') === 0) { var resp = await fetch(userAudio); var blob = await resp.blob();
                        f.append('file', blob, 'audio.wav'); } else throw new Error('不支持的音频格式');
                    var r = await fetch(API_BASE + '/audio/transcriptions', { signal: signal, method: 'POST', headers: { 'Authorization': 'Bearer ' + key }, body: f });
                    if (!r.ok) { var m = 'HTTP ' + r.status; try { var e = await r.json();
                            m = e.message || e.error?.message || m } catch (_) {} throw new Error('ASR ' + node.modelName + ': ' + m); }
                    var j = await r.json();
                    return j.text || '(无识别结果)';
                }
            default:
                return null;
        }
    }

    function saveDataExport(node, dt, val) {
        var h = node.directoryHandle;
        var ts = Date.now();
        var ext = { text: '_output.txt', image: '.png', audio: '.wav', video: '.mp4' } [dt] || '.dat';
        var userFn = (node.downloadPath || '').trim();
        var fname = userFn || (ts + ext);
        if (h && typeof h.getFileHandle === 'function') {
            (async function() {
                try {
                    var fh = await h.getFileHandle(fname, { create: true });
                    var w = await fh.createWritable();
                    if (dt === 'image' && typeof val === 'string' && val.indexOf('data:') === 0) { var r = await fetch(val); var b = await r.blob(); await w.write(b); } else { await w.write(typeof val === 'string' ? val : JSON.stringify(val, null, 2)); }
                    await w.close();
                } catch (e) { showToast('保存失败: ' + e.message, 'error'); }
            })();
        } else {
            var folder = node.saveFolder || 'export';
            var fn = folder + '_' + fname;
            if (dt === 'image' && typeof val === 'string' && val.indexOf('data:') === 0) { var a = document.createElement('a');
                a.href = val;
                a.download = fn;
                a.click(); } else { var blob = new Blob([typeof val === 'string' ? val : JSON.stringify(val, null, 2)], { type: 'text/plain' }); var a = document.createElement('a');
                a.href = URL.createObjectURL(blob);
                a.download = fn;
                a.click();
                URL.revokeObjectURL(a.href); }
        }
    }

    function saveOutputToFile(node, inp, c) {
        var h = node.directoryHandle;
        var userFn = (node.downloadPath || '').trim();
        var ts = Date.now();
        var ext = inp.image ? '.png' : '.txt';
        var fn = userFn || (ts + ext);
        if (h && typeof h.getFileHandle === 'function' && c !== '(无数据)') {
            (async function() {
                try {
                    var fh = await h.getFileHandle(fn, { create: true });
                    var w = await fh.createWritable();
                    if (inp.image && typeof c === 'string' && c.indexOf('data:') === 0) { var r = await fetch(c); var b = await r.blob(); await w.write(b); } else { await w.write(typeof c === 'string' ? c : JSON.stringify(c, null, 2)); }
                    await w.close();
                } catch (e) { showToast('保存失败: ' + e.message, 'error'); }
            })();
        } else {
            if (inp.image && typeof c === 'string' && c.indexOf('data:') === 0) { var a = document.createElement('a');
                a.href = c;
                a.download = fn.replace(/\.[^.]+$/, '') + '.png';
                a.click(); } else { var b = new Blob([typeof c === 'string' ? c : JSON.stringify(c, null, 2)], { type: 'text/plain' }); var a = document.createElement('a');
                a.href = URL.createObjectURL(b);
                a.download = fn;
                a.click();
                URL.revokeObjectURL(a.href); }
        }
    }

    function findLoopPairs() {
        var pairs = [];
        for (var ci = 0; ci < connections.length; ci++) {
            var conn = connections[ci];
            if (conn.fromLabel !== 'next' || conn.toLabel !== 'next') continue;
            var endNode = nodes.find(function(n) { return n.id === conn.fromNodeId; });
            var startNode = nodes.find(function(n) { return n.id === conn.toNodeId; });
            if (!endNode || !startNode || endNode.type !== 'loop-end' || startNode.type !== 'loop-start') continue;
            var bodyNodes = [];
            var visited = {};
            var traverse = function(nid, depth) {
                if (depth > 50 || visited[nid]) return;
                visited[nid] = true;
                if (nid === endNode.id) return;
                if (nid !== startNode.id) bodyNodes.push(nid);
                for (var cj = 0; cj < connections.length; cj++) {
                    var c = connections[cj];
                    if (c.fromNodeId === nid) traverse(c.toNodeId, depth + 1);
                }
            };
            for (var cj = 0; cj < connections.length; cj++) {
                var c = connections[cj];
                if (c.fromNodeId === startNode.id && c.fromLabel === 'body') traverse(c.toNodeId, 0);
            }
            pairs.push({ startId: startNode.id, endId: endNode.id, bodyNodeIds: [...new Set(bodyNodes)] });
        }
        return pairs;
    }

    async function runWorkflow() {
        if (isRunning) return;
        if (!apiKey) { showToast('请先输入 API Key', 'error'); return; }
        if (!nodes.length) { showToast('请添加节点', 'error'); return; }
        isRunning = true;
        stopRequested = false;
        abortController = new AbortController();
        var btn = $('wfRunWorkflowBtn');
        btn.textContent = '⏹ 停止';
        btn.className = 'wf-action-btn warn';
        btn.disabled = false;
        btn.onclick = function() { stopRequested = true;
            abortController?.abort();
            showToast('⏹ 正在停止...', ''); };

        var loopPairs = findLoopPairs();
        var loopBodySet = new Set();
        for (var pi = 0; pi < loopPairs.length; pi++) {
            for (var bj = 0; bj < loopPairs[pi].bodyNodeIds.length; bj++) {
                loopBodySet.add(loopPairs[pi].bodyNodeIds[bj]);
            }
        }
        var loopStartSet = new Set(loopPairs.map(function(p) { return p.startId; }));
        var loopEndSet = new Set(loopPairs.map(function(p) { return p.endId; }));

        var filteredConn = connections.filter(function(c) { return !(c.fromLabel === 'next' && c.toLabel === 'next'); });
        var inDeg = {},
            adj = {};
        nodes.forEach(function(n) { inDeg[n.id] = 0;
            adj[n.id] = []; });
        filteredConn.forEach(function(c) { inDeg[c.toNodeId] = (inDeg[c.toNodeId] || 0) + 1;
            adj[c.fromNodeId].push(c.toNodeId); });
        var sorted = [],
            q = nodes.filter(function(n) { return inDeg[n.id] === 0; }).map(function(n) { return n.id; });
        while (q.length) { var id = q.shift();
            sorted.push(id); for (var ni = 0; ni < (adj[id] || []).length; ni++) { var nb = adj[id][ni];
                inDeg[nb]--; if (inDeg[nb] === 0) q.push(nb); } }
        for (var ni = 0; ni < nodes.length; ni++) { if (sorted.indexOf(nodes[ni].id) < 0) sorted.push(nodes[ni].id); }

        var results = {};
        var hasError = false;
        container.querySelectorAll('.wf-node-card').forEach(function(c) { c.classList.remove('executing', 'executed', 'error', 'loop-iterating'); });

        for (var si = 0; si < sorted.length; si++) {
            var nid = sorted[si];
            if (loopBodySet.has(nid)) continue;
            var node = nodes.find(function(n) { return n.id === nid; });
            if (!node) continue;

            if (node.type === 'loop-start' && loopStartSet.has(nid)) {
                var pair = loopPairs.find(function(p) { return p.startId === nid; });
                if (!pair) {
                    var card = container.querySelector('.wf-node-card[data-node-id="' + nid + '"]');
                    if (card) card.classList.add('executing');
                    try { var r = await executeNode(node, results, apiKey, abortController?.signal);
                        results[nid] = r; if (card) { card.classList.remove('executing');
                            card.classList.add('executed'); } } catch (err) { if (stopRequested) break;
                        hasError = true; if (card) { card.classList.remove('executing');
                            card.classList.add('error'); }
                        showToast('❌ ' + node.modelName + ': ' + err.message, 'error'); }
                    continue;
                }
                var card = container.querySelector('.wf-node-card[data-node-id="' + nid + '"]');
                var endCard = container.querySelector('.wf-node-card[data-node-id="' + pair.endId + '"]');
                var maxIter = Math.min(node.params?.max_iterations || 10, 100);
                var loopData = null;
                for (var ci = 0; ci < connections.length; ci++) {
                    var c = connections[ci];
                    if (c.toNodeId === nid && c.toLabel === 'in' && c.fromLabel !== 'next') {
                        var fn = nodes.find(function(n) { return n.id === c.fromNodeId; });
                        if (fn && results[fn.id] !== undefined) { loopData = results[fn.id]; break; }
                    }
                }
                if (loopData === null) loopData = '（初始数据）';
                for (var iter = 0; iter < maxIter; iter++) {
                    node.params.current_iteration = iter + 1;
                    if (card) { card.classList.add('loop-iterating');
                        card.classList.remove('executed', 'error'); }
                    results[nid] = loopData;
                    var bodyTopo = [];
                    var bInDeg = {},
                        bAdj = {};
                    var allBodyIds = [pair.startId].concat(pair.bodyNodeIds).concat([pair.endId]);
                    for (var bi = 0; bi < allBodyIds.length; bi++) { bInDeg[allBodyIds[bi]] = 0;
                        bAdj[allBodyIds[bi]] = []; }
                    for (var ci = 0; ci < filteredConn.length; ci++) {
                        var c = filteredConn[ci];
                        if (bInDeg.hasOwnProperty(c.fromNodeId) && bInDeg.hasOwnProperty(c.toNodeId)) { bInDeg[c.toNodeId]++;
                            bAdj[c.fromNodeId].push(c.toNodeId); }
                    }
                    var bQ = [pair.startId];
                    while (bQ.length) { var id = bQ.shift();
                        bodyTopo.push(id); for (var ni = 0; ni < (bAdj[id] || []).length; ni++) { var nb = bAdj[id][ni];
                            bInDeg[nb]--; if (bInDeg[nb] === 0) bQ.push(nb); } }
                    for (var bsi = 0; bsi < bodyTopo.length; bsi++) {
                        var bid = bodyTopo[bsi];
                        if (bid === pair.startId) continue;
                        var bn = nodes.find(function(n) { return n.id === bid; });
                        if (!bn) continue;
                        var bCard = container.querySelector('.wf-node-card[data-node-id="' + bid + '"]');
                        if (bCard) bCard.classList.add('executing');
                        try { var br = await executeNode(bn, results, apiKey, abortController?.signal);
                            results[bid] = br; if (bCard) { bCard.classList.remove('executing');
                                bCard.classList.add('executed'); } } catch (err) { if (stopRequested) break;
                            hasError = true; if (bCard) { bCard.classList.remove('executing');
                                bCard.classList.add('error'); }
                            showToast('❌ ' + bn.modelName + ' (迭代 ' + (iter + 1) + '): ' + err.message, 'error'); }
                        if (bn.type === 'output-display' || bn.type === 'data-monitor') renderAll();
                    }
                    loopData = results[pair.endId];
                    if (loopData === undefined) loopData = '（空）';
                    renderAll();
                }
                results[nid] = loopData;
                if (card) { card.classList.remove('loop-iterating');
                    card.classList.add('executed'); }
                if (endCard) endCard.classList.add('executed');
                node.params.current_iteration = maxIter;
                showToast('🔁 循环完成: ' + maxIter + ' 次迭代', 'success');
                continue;
            }

            if (node.type === 'loop-end' && loopEndSet.has(nid)) continue;

            var card = container.querySelector('.wf-node-card[data-node-id="' + nid + '"]');
            if (card) card.classList.add('executing');
            try { var r = await executeNode(node, results, apiKey, abortController?.signal);
                results[nid] = r; if (card) { card.classList.remove('executing');
                    card.classList.add('executed'); } } catch (err) { hasError = true; if (card) { card.classList.remove('executing');
                    card.classList.add('error'); }
                showToast('❌ ' + node.modelName + ': ' + err.message, 'error'); }
            if (node.type === 'output-display' || node.type === 'data-monitor') renderAll();
        }

        isRunning = false;
        stopRequested = false;
        abortController = null;
        btn.textContent = '▶️ 运行工作流';
        btn.className = 'wf-action-btn primary';
        btn.disabled = false;
        btn.onclick = runWorkflow;
        if (!hasError) showToast('✅ 工作流执行完成！', 'success');
        renderAll();
    }

    // ── 侧边栏按钮绑定 ──
    container.querySelectorAll('.wf-media-btn').forEach(function(b) {
        b.addEventListener('click', function() {
            if (b.id === 'wfAddMonitorBtn') { addMonitorNode(); return; }
            if (b.id === 'wfAddExportBtn') { addExportNode(); return; }
            addMediaNode(b.dataset.media);
        });
    });
    container.querySelectorAll('.wf-output-btn').forEach(function(b) {
        b.addEventListener('click', function() { addOutputNode(b.dataset.output); });
    });
    $('wfAddLoopStartBtn').addEventListener('click', addLoopStartNode);
    $('wfAddLoopEndBtn').addEventListener('click', addLoopEndNode);

    // ── API Key & 模型加载 ──
    apiKeyInput.value = apiKey;
    apiKeyInput.addEventListener('input', function() { apiKey = apiKeyInput.value.trim();
        localStorage.setItem('sf_api_key', apiKey); });

    async function loadModels() {
        var key = apiKeyInput.value.trim();
        if (!key) { apiStatus.textContent = '⚠️ 请先输入 API Key';
            apiStatus.className = 'wf-api-status error'; return; }
        apiKey = key;
        localStorage.setItem('sf_api_key', key);
        var cached = loadCachedModels();
        if (cached && cached.length) { fetchedModels = cached;
            renderSidebarModels();
            apiStatus.textContent = '📦 从缓存加载了 ' + cached.length + ' 个模型';
            apiStatus.className = 'wf-api-status success'; }
        loadModelsBtn.disabled = true;
        apiStatus.textContent = '⏳ 正在从 SiliconFlow 获取模型列表...';
        apiStatus.className = 'wf-api-status loading';
        try {
            var fresh = await fetchModelsFromAPI(key);
            if (fresh && fresh.length) { fetchedModels = fresh;
                renderSidebarModels();
                apiStatus.textContent = '✅ 成功加载 ' + fresh.length + ' 个模型 (' + new Date().toLocaleTimeString() + ')';
                apiStatus.className = 'wf-api-status success';
                showToast('已加载 ' + fresh.length + ' 个模型', 'success'); } else if (!cached || !cached.length) { apiStatus.textContent = '⚠️ API 返回为空';
                apiStatus.className = 'wf-api-status error'; }
        } catch (err) {
            if (!cached || !cached.length) { apiStatus.textContent = '❌ 加载失败: ' + err.message;
                apiStatus.className = 'wf-api-status error';
                showToast('加载失败: ' + err.message, 'error'); } else { apiStatus.textContent = '⚠️ API 刷新失败，使用缓存中';
                apiStatus.className = 'wf-api-status'; }
        } finally { loadModelsBtn.disabled = false; }
    }
    loadModelsBtn.addEventListener('click', loadModels);
    clearCacheBtn.addEventListener('click', function() {
        localStorage.removeItem(CACHE_KEY);
        localStorage.removeItem(CACHE_TIME_KEY);
        fetchedModels = [];
        renderSidebarModels();
        apiStatus.textContent = '已清除模型缓存';
        apiStatus.className = 'wf-api-status';
        showToast('缓存已清除', '');
    });

    // ── 工作流管理 ──
    function serializeWorkflow() { saveCurrentWs(); return JSON.stringify({ version: '1.0', workspaces: workspaces }, null, 2); }

    function deserializeWorkflow(json) {
        try {
            var d = typeof json === 'string' ? JSON.parse(json) : json;
            if (d.workspaces && d.workspaces.length) {
                workspaces = d.workspaces.map(function(w) { return Object.assign({}, w, { nodes: (w.nodes || []).map(function(n) { return Object.assign({}, n, { fileData: null }); }) }); });
                currentWs = 0;
                var ws = workspaces[0];
                nodes = ws.nodes;
                connections = ws.connections;
                nodeIdCounter = ws.nodeIdCounter || nodes.length;
                selectedNodeId = null;
                canvasPan = ws.canvasPan || { x: 0, y: 0 };
                canvasZoom = ws.canvasZoom || 1;
            } else if (d.nodes) {
                workspaces = [{ name: '工作流 1', nodes: d.nodes.map(function(n) { return Object.assign({}, n, { fileData: null }); }), connections: d.connections, nodeIdCounter: d.nodeIdCounter || d.nodes.length, selectedNodeId: null, canvasPan: { x: 0, y: 0 }, canvasZoom: 1 }];
                currentWs = 0;
                nodes = workspaces[0].nodes;
                connections = workspaces[0].connections;
                nodeIdCounter = workspaces[0].nodeIdCounter;
            } else throw new Error('无效的工作流文件');
            applyCanvasTransform();
            renderAll();
            renderTabBar();
            showToast('已加载工作流 (' + workspaces.length + ' 工作台)', 'success');
        } catch (err) { showToast('加载失败: ' + err.message, 'error'); }
    }
    $('wfSaveWfBtn').addEventListener('click', function() {
        if (!nodes.length) { showToast('画布为空', 'error'); return; }
        var j = serializeWorkflow();
        var b = new Blob([j], { type: 'application/json' });
        var a = document.createElement('a');
        a.href = URL.createObjectURL(b);
        a.download = 'workflow-' + Date.now() + '.json';
        a.click();
        URL.revokeObjectURL(a.href);
        showToast('工作流已保存', 'success');
    });
    $('wfLoadWfBtn').addEventListener('click', function() { wfFileInput.click(); });
    wfFileInput.addEventListener('change', function(e) {
        if (e.target.files[0]) {
            var r = new FileReader();
            r.onload = function(ev) { try { deserializeWorkflow(ev.target.result) } catch (err) { showToast('文件解析失败: ' + err.message, 'error'); } };
            r.readAsText(e.target.files[0]);
            e.target.value = '';
        }
    });

    var autoSaveToggle = $('wfAutoSaveToggle');
    autoSaveToggle.addEventListener('click', function() {
        autoSaveEnabled = !autoSaveEnabled;
        autoSaveToggle.textContent = autoSaveEnabled ? '⏸ 自动保存: 开' : '▶️ 自动保存: 关';
        showToast(autoSaveEnabled ? '自动保存已开启' : '自动保存已关闭', '');
    });
    var autoSaveTimer = null;

    function scheduleAutoSave() {
        clearTimeout(autoSaveTimer);
        autoSaveTimer = setTimeout(function() {
            if (!autoSaveEnabled) return;
            try { saveCurrentWs();
                localStorage.setItem(AUTO_SAVE_KEY, serializeWorkflow()) } catch (_) {}
        }, 2000);
    }

    function tryAutoRestore() {
        try { var s = localStorage.getItem(AUTO_SAVE_KEY); if (s) { var d = JSON.parse(s); if (d.workspaces || d.nodes) deserializeWorkflow(d); } } catch (_) {}
    }

    $('wfClearAllBtn').addEventListener('click', function() {
        if (!nodes.length) return;
        if (confirm('确定清空画布？')) { nodes = [];
            connections = [];
            selectedNodeId = null;
            renderAll(); }
    });
    $('wfFitViewBtn').addEventListener('click', fitView);
    $('wfRunWorkflowBtn').addEventListener('click', runWorkflow);

    // ── 画布交互 ──
    canvasContainer.addEventListener('click', function(e) {
        if (e.target.classList.contains('wf-conn-line') && e.target.dataset.connIdx !== undefined) {
            var idx = parseInt(e.target.dataset.connIdx);
            if (!isNaN(idx) && idx >= 0 && idx < connections.length) { connections.splice(idx, 1);
                renderAll();
                scheduleAutoSave(); return; }
        }
        if (e.target === canvasContainer || e.target.id === 'wfNodesLayer' || e.target.id === 'wfLineLayer' || e.target === canvasViewport) { selectedNodeId = null;
            renderAll(); }
    });
    canvasContainer.addEventListener('wheel', function(e) {
        e.preventDefault();
        var r = canvasContainer.getBoundingClientRect();
        zoomCanvas(e.deltaY > 0 ? 0.9 : 1.1, e.clientX, e.clientY);
    }, { passive: false });
    var midPan = { active: false, sx: 0, sy: 0, px: 0, py: 0 };
    canvasContainer.addEventListener('mousedown', function(e) {
        if (e.button === 1) { e.preventDefault();
            midPan = { active: true, sx: e.clientX, sy: e.clientY, px: canvasPan.x, py: canvasPan.y };
            canvasContainer.style.cursor = 'grabbing'; }
    });
    window.addEventListener('mousemove', function(e) {
        if (midPan.active) { canvasPan.x = midPan.px + (e.clientX - midPan.sx);
            canvasPan.y = midPan.py + (e.clientY - midPan.sy);
            applyCanvasTransform(); }
    });
    window.addEventListener('mouseup', function(e) {
        if (e.button === 1 && midPan.active) { midPan.active = false;
            canvasContainer.style.cursor = 'grab'; }
    });

    // ── 快捷键 ──
    var _keyHandler = function(e) {
        // 仅在 workflow 页面可见时处理快捷键
        if (!container.offsetParent) return;
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;
        if ((e.key === 'Delete' || e.key === 'Backspace') && selectedNodeId) { e.preventDefault();
            deleteNode(selectedNodeId); }
        if ((e.ctrlKey || e.metaKey) && e.key === 'd') { e.preventDefault(); if (selectedNodeId) duplicateNode(selectedNodeId); }
        if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault();
            $('wfSaveWfBtn').click(); }
        if (e.key === 'Escape') { selectedNodeId = null;
            renderAll(); }
    };
    document.addEventListener('keydown', _keyHandler);

    // ── 初始化 ──
    $('wfModelSearchInput')?.addEventListener('input', function() { renderSidebarModels(); });

    var cached = loadCachedModels();
    if (cached && cached.length) { fetchedModels = cached;
        renderSidebarModels();
        apiStatus.textContent = '📦 已加载 ' + cached.length + ' 个模型 (缓存)';
        apiStatus.className = 'wf-api-status success'; } else renderSidebarModels();

    tryAutoRestore();
    if (!workspaces[0].nodes.length) {
        var t = createNode('media-text', null, 50, 40);
        if (t) { t.textContent = '';
            nodes.push(t); }
        var ls = createNode('loop-start', null, 240, 100);
        if (ls) { ls.params = { max_iterations: 3, current_iteration: 0 };
            nodes.push(ls); }
        var c = createNode('chat', { id: 'deepseek-ai/DeepSeek-V3', _shortName: 'DeepSeek-V3', _category: 'chat', owned_by: 'deepseek-ai' }, 200, 240);
        if (c) { c.systemPrompt = '你是一个有帮助的助手。请用中文回答。';
            nodes.push(c); }
        var le = createNode('loop-end', null, 400, 300);
        if (le) nodes.push(le);
        var d = createNode('output-display', null, 560, 200);
        if (d) nodes.push(d);
        saveCurrentWs();
    }

    // ── Tab 栏 ──
    function renderTabBar() {
        var bar = $('wfTabBar');
        if (!bar) return;
        var h = '';
        for (var i = 0; i < workspaces.length; i++) {
            var ws = workspaces[i];
            h += '<div class="wf-tab' + (i === currentWs ? ' active' : '') + '" data-idx="' + i + '"><span>' + escapeHtml(ws.name) + '</span><span class="wf-tab-close" data-idx="' + i + '">✕</span></div>';
        }
        h += '<button class="wf-tab-add-btn" title="新建工作台">+</button>';
        bar.innerHTML = h;
        bar.querySelectorAll('.wf-tab').forEach(function(el) {
            el.addEventListener('click', function(e) { if (e.target.classList.contains('wf-tab-close')) return;
                switchWorkspace(parseInt(el.dataset.idx)); });
        });
        bar.querySelectorAll('.wf-tab-close').forEach(function(el) {
            el.addEventListener('click', function(e) { e.stopPropagation();
                removeWorkspace(parseInt(el.dataset.idx)); });
        });
        bar.querySelector('.wf-tab-add-btn')?.addEventListener('click', addWorkspace);
    }

    renderTabBar();
    applyCanvasTransform();
    renderAll();
    setTimeout(fitView, 150);

    // ── 清理（页面销毁时可调用） ──
    container._cleanup = function() {
        document.removeEventListener('keydown', _keyHandler);
        var toast = document.getElementById('wf-toast-fixed');
        if (toast) toast.remove();
    };
}
