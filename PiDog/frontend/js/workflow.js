/* ============================================================
   workflow.js — AI 内容生成工作流（硅基流动 · 循环执行）
   完整模块化适配 PiDog 前端
   本质：可视化 DAG 节点编辑器 + API 调用执行引擎
   ============================================================ */

function renderWorkflowPage(container) {
    // ── DOM 辅助 ──
    function $(id) { return container.querySelector('#' + id); }

    // ── 提供商配置 ──
    var PROVIDERS = {
        siliconflow: { name: '硅基流动', icon: '✨', base_url: 'https://api.siliconflow.cn/v1', api_key_storage: 'sf_api_key', model_cache: 'sf_models_cache', cache_time: 'sf_models_cache_time' },
        bailian:     { name: '阿里云百炼', icon: '☁️', base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', api_key_storage: 'bl_api_key', model_cache: 'bl_models_cache', cache_time: 'bl_models_cache_time' },
    };
    var selectedProvider = localStorage.getItem('wf_selected_provider') || 'siliconflow';
    function curProv() { return PROVIDERS[selectedProvider] || PROVIDERS.siliconflow; }
    var CACHE_DURATION = 10 * 60 * 1000, AUTO_SAVE_KEY = 'sf_workflow_autosave';

    // ── 状态 ──
    var nodes = [], connections = [], nodeIdCounter = 0, selectedNodeId = null;
    var dragState = { active: false, nodeId: null, offsetX: 0, offsetY: 0 };
    var connectDrag = { active: false, fromNodeId: null, fromPortId: null, fromPortType: null, currentX: 0, currentY: 0 };
    var isRunning = false, stopRequested = false, abortController = null, autoSaveEnabled = true, canvasPan = { x: 0, y: 0 }, canvasZoom = 1, fetchedModels = [];
    var apiKey = localStorage.getItem(curProv().api_key_storage) || '';
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
        '    <div class="wf-sidebar-header">' +
        '      <select id="wfProviderSelect" style="background:transparent;border:none;color:#fff;font-weight:600;font-size:15px;cursor:pointer;outline:none;">' +
        '        <option value="siliconflow" style="background:#2a2a33;color:#fff;">✨ 硅基流动</option>' +
        '        <option value="bailian" style="background:#2a2a33;color:#fff;">☁️ 阿里云百炼</option>' +
        '      </select>' +
        '      <span style="color:#a0a0b8;">· 模型广场</span>' +
        '    </div>' +
        '    <div class="wf-api-section">' +
        '      <input type="password" id="wfApiKeyInput" placeholder="输入 SiliconFlow API Key ..." />' +
        '      <div class="wf-api-actions">' +
        '        <button id="wfLoadModelsBtn">🔄 加载模型广场</button>' +
        '        <button id="wfClearCacheBtn" style="background:#4a4a5a;flex:0.4">清空缓存</button>' +
        '      </div>' +
        '      <div class="wf-api-status" id="wfApiStatus">输入 API Key 后点击加载</div>' +
        '    </div>' +
        '    <div class="wf-sidebar-views" id="wfSidebarViews">' +
        '      <div id="wfSidebarMainView">' +
        '    <div class="wf-category">📂 工作流管理</div>' +
        '    <div class="wf-row">' +
        '        <button id="wfSaveWfBtn">💾 保存到文件</button>' +
        '        <button id="wfLoadWfBtn">📂 加载工作流</button>' +
        '      </div>' +
        '      <div class="wf-row">' +
        '        <button id="wfAutoSaveToggle">⏸ 自动保存: 开</button>' +
        '      </div>' +
        '      <div class="wf-row">' +
        '        <button id="wfAssetsBtn">📂 工作流资产</button>' +
        '      </div>' +
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
        '      </div>' +
        '      <div id="wfSidebarAssetsView" style="display:none;">' +
        '        <div class="wf-sidebar-view-header">' +
        '          <button id="wfAssetsBackBtn" class="wf-back-btn">← 返回</button>' +
        '          <span>📂 工作流资产</span>' +
        '        </div>' +
        '        <div id="wfAssetsContainer" class="wf-assets-container" style="max-height:none;">' +
        '          <div class="wf-no-models">运行工作流后自动保存资产</div>' +
        '        </div>' +
        '      </div>' +
        '    </div>' +
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
    function categorizeModelId(id, caps) {
        var cats = [];

        // ── 第1优先级：API capabilities 收集所有匹配类别 ──
        if (caps) {
            if (caps.image_generation)   cats.push('image-gen');
            if (caps.video_generation)   cats.push('video-gen');
            if (caps.text_to_speech)     cats.push('tts');
            if (caps.audio_transcription || caps.speech_recognition) cats.push('asr');
            if (caps.multimodal_chat || caps.image_recognition) cats.push('image-understand');
            // 如果有任何专门能力，chat_completion 也附加（但不作为唯一的）
            if (caps.chat_completion && cats.length > 0) cats.push('chat');
            // 只有 chat_completion 没有其它能力 → 纯对话模型
            if (caps.chat_completion && cats.length === 0) cats.push('chat');
            if (cats.length > 0) return cats;
        }

        // ── 第2优先级：模型 ID 正则匹配（用于无 capabilities 的提供商） ──
        var i = id.toLowerCase();

        // 过滤掉嵌入/重排模型
        if (/embedding|rerank|bge|bce-embedding|gte|text2vec/.test(i)) return [];

        if (/kling|cogvideo|videocrafter|modelscope.*t2v|text2video|t2v-|video-gen|wan.*video/.test(i)) cats.push('video-gen');
        if (/video-llama|videochat|valley|video-blip|internvideo|video-llava/.test(i)) cats.push('video-understand');
        if (/stable-diffusion|sdxl|sd3|sana|flux|pixart|kolors|latent-consistency|wurstchen|deepfloyd|lumina|auraflow|dall-e|playground|wanx|imagen|image/.test(i)) cats.push('image-gen');
        if (/[-.]vl\d?$|[-.]vl[-.]|vision|internvl|cogvlm|deepseek[-.]vl|qwen[\d.]*-vl|minicpmv|glm-4v|llava|yi[-.]vl|openbmb.*vl|phi.*vision/.test(i)) cats.push('image-understand');
        if (/ocr|got-|image-to-text|img2txt|visual.*qa|.*grounding|detection|segmentation|sam-|clip-|imagebind|image-editor|inpainting|outpainting/.test(i)) cats.push('vision');
        if (/cosyvoice|tts-?1|fishtalk|chattts|gptsovits|bark|vall-e/.test(i)) cats.push('tts');
        if (/whisper|sensevoice|parakeet|asr|speech.?recog|voice.?recog|transcri/.test(i)) cats.push('asr');
        if (/deepseek.*r1|qwq|reasoning|deep.*think|o1-|o3-/.test(i)) cats.push('reasoning');

        // 有匹配到专门类别 → 同时附加 chat（多模态模型也可对话）
        if (cats.length > 0) {
            cats.push('chat');
            return cats;
        }

        return ['chat'];
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
            case 'tts': return { voice: 'alex', speed: 1.0 };
            case 'asr': return { language: 'auto' };
            default: return {};
        }
    }

    function getPortsByType(type) {
        var P = {
            'chat': { i: ['text'], o: ['text'] },
            'reasoning': { i: ['text'], o: ['text'] },
            'image-gen': { i: ['text', 'image', 'image2', 'image3'], o: ['image'] },
            'image-understand': { i: ['image', 'image2', 'image3', 'text'], o: ['text'] },
            'vision': { i: ['image', 'image2', 'image3', 'text'], o: ['text'] },
            'video-gen': { i: ['text', 'image', 'image2', 'image3'], o: ['video'] },
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
        var prov = curProv();
        var r = await fetch(prov.base_url + '/models', { headers: { 'Authorization': 'Bearer ' + key } });
        if (!r.ok) { var m = 'HTTP ' + r.status; try { var e = await r.json(); m = e.message || e.error?.message || m } catch (_) {} throw new Error(m); }
        var d = await r.json(),
            raw = d.data || [];
        var cat = raw.map(function(m) {
            var caps = m.capabilities || {}; return { id: m.id, owned_by: m.owned_by || getOwner(m.id), capabilities: caps, _categories: categorizeModelId(m.id, caps), _shortName: getShortName(m.id) };
        }).filter(function(m) { return m._categories && m._categories.length > 0; });
        try { localStorage.setItem(prov.model_cache, JSON.stringify(cat));
            localStorage.setItem(prov.cache_time, String(Date.now())) } catch (_) {}
        return cat;
    }

    function loadCachedModels() { try { var prov = curProv(); var c = localStorage.getItem(prov.model_cache),
                t = localStorage.getItem(prov.cache_time); if (c && t && (Date.now() - Number(t)) < CACHE_DURATION) return JSON.parse(c) } catch (_) {} return null; }

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
            nodeData.type = type;
            nodeData.params = JSON.parse(JSON.stringify(getDefaultParams(type)));
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
            else if (node.type === 'tts') body.innerHTML = buildTTSBody(node);
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
                if (e.target.classList.contains('wf-delete-node') || e.target.closest('.wf-port') || e.target.closest('input') || e.target.closest('textarea') || e.target.closest('select')) return;
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
        container.querySelectorAll('select[data-param]').forEach(function(sel) {
            sel.addEventListener('change', function() {
                var n = nodes.find(function(x) { return x.id === sel.dataset.node; });
                if (n && n.params) { n.params[sel.dataset.param] = sel.value;
                    scheduleAutoSave(); }
            });
        });
        container.querySelectorAll('.wf-system-prompt').forEach(function(ta) {
            ta.addEventListener('input', function() {
                var n = nodes.find(function(x) { return x.id === ta.dataset.node; });
                if (n) { n.systemPrompt = ta.value;
                    scheduleAutoSave(); }
            });
        });
        container.querySelectorAll('.wf-custom-voice-input').forEach(function(inp) {
            inp.addEventListener('input', function() {
                var n = nodes.find(function(x) { return x.id === inp.dataset.node; });
                if (n) { if (!n.params) n.params = {}; n.params.custom_voice = inp.value;
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
        var fileStatusHtml = n.fileData
            ? '<div style="color:#8f8;font-size:11px;margin-bottom:4px;">✅ ' + escapeHtml(n.fileData.name) + '</div>'
            : '';
        return '<div class="wf-param-row"><label>📎 上传' + n.mediaType.toUpperCase() + '文件</label>' + fileStatusHtml + '<input type="file" accept="' + (a[n.mediaType] || '*') + '" data-node="' + n.id + '" class="wf-file-input" /></div>';
    }

    function renderContentByType(n) {
        var c = n.savedContent;
        if (!c) return '等待输入...';
        var t = n.savedContentType || 'text';
        if (t === 'image') return '<img src="' + c + '" alt="输出" style="max-width:100%;max-height:140px;border-radius:4px;" />';
        if (t === 'audio') return '<audio controls src="' + c + '" style="width:100%;height:40px;">您的浏览器不支持音频播放</audio>';
        if (t === 'video') return '<video controls src="' + c + '" style="max-width:100%;max-height:140px;border-radius:4px;">您的浏览器不支持视频播放</video>';
        return typeof c === 'string' ? escapeHtml(c) : escapeHtml(JSON.stringify(c, null, 2));
    }

    function buildOutputDisplayBody(n) {
        return '<div class="wf-param-row"><label>📺 接收内容预览</label><div class="wf-output-display" data-node="' + n.id + '">' + renderContentByType(n) + '</div></div>';
    }

    function buildOutputSaveBody(n) {
        var dirName = n.directoryHandle?.name || n._dirName || '未选择';
        var fname = n.downloadPath || 'output.txt';
        return '<div class="wf-param-row"><label>📁 保存目录</label><div style="display:flex;gap:4px;"><span style="flex:1;background:#1e1e26;border:1px solid #4a4a56;color:white;padding:5px 8px;border-radius:5px;font-size:12px;overflow:hidden;text-overflow:ellipsis;">' + escapeHtml(dirName) + '</span><button class="wf-dir-pick-btn" data-node="' + n.id + '">📂 选择</button></div></div><div class="wf-param-row"><label>💾 文件名（留空自动生成）</label><input type="text" value="' + escapeHtml(fname) + '" placeholder="留空自动生成" data-param="filename" data-node="' + n.id + '"/></div>';
    }

    function buildDataMonitorBody(n) {
        return '<div class="wf-param-row"><label>📊 流经数据预览</label><div class="wf-output-display" style="border-color:#6a4a6a;" data-node="' + n.id + '">' + renderContentByType(n) + '</div></div>';
    }

    function buildDataExportBody(n) {
        var dirName = n.directoryHandle?.name || n._dirName || '未选择';
        var fname = n.downloadPath || '';
        return '<div class="wf-param-row"><label>📁 保存目录</label><div style="display:flex;gap:4px;"><span style="flex:1;background:#1e1e26;border:1px solid #4a4a56;color:white;padding:5px 8px;border-radius:5px;font-size:12px;overflow:hidden;text-overflow:ellipsis;">' + escapeHtml(dirName) + '</span><button class="wf-dir-pick-btn" data-node="' + n.id + '">📂 选择</button></div></div><div class="wf-param-row"><label>💾 文件名（留空自动生成）</label><input type="text" value="' + escapeHtml(fname) + '" placeholder="留空自动生成" data-param="filename" data-node="' + n.id + '"/></div><div class="wf-param-row"><label>💾 最后保存内容</label><div class="wf-output-display" style="border-color:#3a5a4a;" data-node="' + n.id + '">' + renderContentByType(n) + '</div></div>';
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

    // ── TTS 音色注册表 ──
    // 硅基流动 CosyVoice 系列实际音色为英文名
    var TTS_VOICES = {
        'cosyvoice': ['alex', 'bella', 'benjamin', 'charles', 'claire', 'david', 'emma', 'james', 'lily', 'sarah', 'william'],
        'chattts': ['female-1', 'male-1', 'child-1'],
        'gptsovits': ['zh_female', 'zh_male', 'en_female', 'en_male', 'jp_female'],
        'bark': ['v2/en_speaker_1', 'v2/en_speaker_2', 'v2/zh_speaker_1'],
        '__default__': ['zh_female', 'zh_male', 'en_female', 'en_male'],
    };

    function getTTSVoices(modelId) {
        var id = (modelId || '').toLowerCase();
        for (var key in TTS_VOICES) {
            if (key !== '__default__' && id.indexOf(key) >= 0) return TTS_VOICES[key];
        }
        return TTS_VOICES['__default__'];
    }

    // 异步获取 TTS 音色（如有专用 endpoint 则覆盖硬编码列表，目前作为扩展点）
    var _voiceCache = {};
    async function tryFetchTTSVoices(modelId, apiKey) {
        if (!modelId || !apiKey) return null;
        var prov = curProv();
        var cacheKey = modelId + '@' + prov.name;
        if (_voiceCache[cacheKey]) return _voiceCache[cacheKey];
        try {
            var r = await fetch(prov.base_url + '/audio/voices', {
                headers: { 'Authorization': 'Bearer ' + apiKey }
            });
            if (r.ok) {
                var d = await r.json();
                var list = (d.data || d.voices || []).map(function(v) { return typeof v === 'string' ? v : (v.id || v.name || v.voice_id || ''); }).filter(Boolean);
                if (list.length > 0) { _voiceCache[cacheKey] = list; return list; }
            }
        } catch (_) {}
        return null;
    }

    function buildTTSBody(n) {
        var voices = getTTSVoices(n.modelId);
        var customVoice = (n.params && n.params.custom_voice) || '';
        var curVoice = (n.params && n.params.voice) || voices[0] || 'alex';
        if (voices.indexOf(curVoice) < 0 && !customVoice) curVoice = voices[0];
        var h = '<div class="wf-param-row"><label>📝 待合成文本</label><textarea class="wf-system-prompt" data-node="' + n.id + '" placeholder="输入要合成的文本 ..." style="min-height:48px;">' + escapeHtml(n.systemPrompt || '') + '</textarea></div>';
        h += '<div class="wf-param-row"><label>🎙️ 音色</label><select data-param="voice" data-node="' + n.id + '" style="background:#1e1e26;border:1px solid #4a4a56;color:white;padding:6px 8px;border-radius:5px;font-size:12px;width:100%;">';
        for (var vi = 0; vi < voices.length; vi++) {
            var v = voices[vi];
            h += '<option value="' + v + '"' + (v === curVoice && !customVoice ? ' selected' : '') + '>' + v + '</option>';
        }
        h += '</select></div>';
        h += '<div class="wf-param-row"><label>✏️ 自定义音色（留空则使用上方选择）</label><input type="text" class="wf-custom-voice-input" data-node="' + n.id + '" value="' + escapeHtml(customVoice) + '" placeholder="输入音色名，如 alex" style="background:#1e1e26;border:1px solid #4a4a56;color:white;padding:6px 8px;border-radius:5px;font-size:12px;width:100%;"/></div>';
        var spd = (n.params && n.params.speed) || 1.0;
        h += '<div class="wf-param-row"><label>⚡ 语速</label><input type="text" value="' + escapeHtml(String(spd)) + '" data-param="speed" data-node="' + n.id + '"/></div>';
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
    function showToast(msg, type) {
        toastEl.textContent = msg;
        toastEl.className = 'wf-toast-fixed show' + (type ? ' ' + type : '');
        clearTimeout(toastEl._timer);
        toastEl._timer = setTimeout(function() {
            toastEl.className = 'wf-toast-fixed';
        }, 4000);
    }

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
            var mds = fetchedModels.filter(function(m) { return m._categories && m._categories.indexOf(cat.key) >= 0; });
            if (!mds.length) continue;
            if (q) mds = mds.filter(function(m) { return m._shortName.toLowerCase().indexOf(q) >= 0 || m.id.toLowerCase().indexOf(q) >= 0 || (m.owned_by && m.owned_by.toLowerCase().indexOf(q) >= 0); });
            if (!mds.length) continue;
            total += mds.length;
            var open = isSearching || collapsedCats[cat.key] !== false;
            html += '<div class="wf-category" data-cat-key="' + cat.key + '"><span class="wf-cat-toggle ' + (open ? 'open' : '') + '">▶</span> ' + cat.icon + ' ' + cat.label + ' <span class="wf-model-count">(' + mds.length + ')</span></div><div class="wf-dynamic-models-scroll ' + (open ? '' : 'collapsed') + '">';
            for (var mi = 0; mi < mds.length; mi++) {
                var m = mds[mi];
                html += '<button class="wf-model-btn" data-model-id="' + escapeHtml(m.id) + '" data-cat="' + cat.key + '"><span class="wf-model-icon">' + cat.icon + '</span><span class="wf-model-info"><span class="wf-model-name">' + escapeHtml(m._shortName) + '</span><span class="wf-model-provider">' + escapeHtml(m.owned_by || '') + '</span></span></button>';
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
            btn.addEventListener('click', function(e) { e.stopPropagation(); var m = fetchedModels.find(function(x) { return x.id === btn.dataset.modelId; }); if (m) { var t = getNodeTypeForModel(m); m._nodeType = t; startPlacement(t, m); } });
        });
    }

    // ── 节点操作 ──
    function selectNode(id) {
        selectedNodeId = id;
        // 仅更新 class 不重建 DOM，避免文件输入等状态丢失
        container.querySelectorAll('.wf-node-card').forEach(function(c) {
            c.classList.toggle('selected', c.dataset.nodeId === id);
        });
    }

    // ── 节点放置模式（点击侧边栏 → 幽灵跟随 → 点击画布放置） ──
    var placeState = null;

    function startPlacement(type, modelData) {
        cancelPlacement();
        var ghost = document.createElement('div');
        ghost.className = 'wf-node-card wf-node-ghost';
        var icon = TYPE_ICONS[type] || '🔹';
        var name = modelData ? (modelData._shortName || modelData.modelName || type) : (TYPE_LABELS[type] || type);
        ghost.innerHTML = '<div class="wf-node-header"><span>' + icon + ' ' + escapeHtml(name) + '</span></div><div class="wf-node-body" style="padding:30px 10px;text-align:center;color:#888;font-size:11px;">点击画布放置</div>';
        ghost.style.cssText = 'position:absolute;pointer-events:none;opacity:0.65;z-index:999;';
        var nl = $('wfNodesLayer');
        if (nl) nl.appendChild(ghost);
        placeState = { type: type, modelData: modelData, ghostEl: ghost };
        showToast('🖱 点击画布放置节点，按 Esc 取消', '');
    }

    function cancelPlacement() {
        if (placeState && placeState.ghostEl) {
            placeState.ghostEl.remove();
        }
        placeState = null;
    }

    function placeNodeAt(x, y) {
        if (!placeState) return;
        var node = createNode(placeState.type, placeState.modelData, x, y);
        if (node) { nodes.push(node); renderAll(); scheduleAutoSave(); }
        cancelPlacement();
    }

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

    function getNodeTypeForModel(md) {
        if (!md) return 'chat';
        var caps = md.capabilities || {};
        var id = (md.id || '').toLowerCase();

        // 第1优先级：capabilities（最准确）
        if (caps.image_generation) return 'image-gen';
        if (caps.video_generation) return 'video-gen';
        if (caps.text_to_speech) return 'tts';
        if (caps.speech_recognition || caps.audio_transcription) return 'asr';
        if (caps.multimodal_chat || caps.image_recognition) return 'image-understand';

        // 第2优先级：模型 ID 特征检测（独立于分类器，确保覆盖面更全）
        if (/stable-diffusion|sdxl|sd3|sana|flux|pixart|kolors|latent-consistency|wurstchen|deepfloyd|lumina|auraflow|dall-e|playground|wanx|imagen|image/.test(id)) return 'image-gen';
        if (/kling|cogvideo|videocrafter|modelscope.*t2v|text2video|t2v-|video-gen|wan.*video/.test(id)) return 'video-gen';
        if (/video-llama|videochat|valley|video-blip|internvideo|video-llava/.test(id)) return 'video-understand';
        if (/[-.]vl\d?$|[-.]vl[-.]|vision|internvl|cogvlm|deepseek[-.]vl|qwen[\d.]*-vl|minicpmv|glm-4v|llava|yi[-.]vl|openbmb.*vl|phi.*vision/.test(id)) return 'image-understand';
        if (/cosyvoice|tts-?1|fishtalk|chattts|gptsovits|bark|vall-e/.test(id)) return 'tts';
        if (/whisper|sensevoice|parakeet|asr|speech.?recog|voice.?recog|transcri/.test(id)) return 'asr';
        if (/deepseek.*r1|qwq|reasoning|deep.*think|o1-|o3-/.test(id)) return 'reasoning';

        return 'chat';
    }

    function addModelNode(md, nodeType) {
        // 始终以模型自身能力生成节点，绕开分类不准的问题
        var t = getNodeTypeForModel(md);
        var n = createNode(t, md, 180 + Math.random() * 220, 100 + Math.random() * 180);
        if (n) { nodes.push(n);
            renderAll(); }
    }

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
            // 仅更新拖拽节点的位置 + 连线，避免全量重建导致文件输入丢失
            var card = container.querySelector('.wf-node-card[data-node-id="' + n.id + '"]');
            if (card) {
                card.style.left = n.x + 'px';
                card.style.top = n.y + 'px';
            }
            renderLines();
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
                        var sameImg = fp.label.indexOf('image') === 0 && tp2.label.indexOf('image') === 0;
                        var canConnect = fp.label === tp2.label || sameImg || LOOP_LABELS.indexOf(fp.label) >= 0 || LOOP_LABELS.indexOf(tp2.label) >= 0;
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
                pendingAssets.push({ nodeId: node.id, type: node.type, modelName: node.modelName, category: 'monitor', contentType: dt || 'text', content: val, ts: Date.now() });
            }
            return val;
        }
        if (node.type === 'data-monitor') {
            var dt = inp.text !== undefined ? 'text' : inp.image !== undefined ? 'image' : inp.audio !== undefined ? 'audio' : inp.video !== undefined ? 'video' : null;
            var c = dt ? inp[dt] : null;
            node.savedContent = c;
            node.savedContentType = dt;
            if (c !== null && c !== undefined) pendingAssets.push({ nodeId: node.id, type: node.type, modelName: node.modelName, category: 'monitor', contentType: dt || 'text', content: c, ts: Date.now() });
            return c;
        }
        if (node.type === 'output-display') { node.savedContent = inp.text || inp.image || inp.audio || inp.video || '(无数据)';
            node.savedContentType = inp.image ? 'image' : inp.audio ? 'audio' : inp.video ? 'video' : 'text';
            pendingAssets.push({ nodeId: node.id, type: node.type, modelName: node.modelName, category: 'output', contentType: node.savedContentType, content: node.savedContent, ts: Date.now() });
            return node.savedContent; }
        if (node.type === 'output-save') {
            var c = inp.text || inp.image || inp.audio || inp.video || '(无数据)';
            node.savedContent = c;
            node.savedContentType = inp.image ? 'image' : inp.audio ? 'audio' : inp.video ? 'video' : 'text';
            saveOutputToFile(node, inp, c);
            pendingAssets.push({ nodeId: node.id, type: node.type, modelName: node.modelName, category: 'output', contentType: node.savedContentType, content: c, ts: Date.now() });
            return c;
        }
        var userText = inp.text || '',
            userImages = [inp.image, inp.image2, inp.image3].filter(function(x) { return x; }),
            userImage = userImages[0] || null,
            userAudio = inp.audio || null;
        switch (node.type) {
            case 'chat':
            case 'reasoning':
                {
                    var msgs = [];
                    if (node.systemPrompt) msgs.push({ role: 'system', content: node.systemPrompt });
                    msgs.push({ role: 'user', content: userText || '你好' });
                    var b = { model: node.modelId, messages: msgs, temperature: node.params?.temperature ?? 0.7, max_tokens: node.params?.max_tokens ?? 2048, stream: false };
                    var r = await fetch(curProv().base_url + '/chat/completions', { signal: signal, method: 'POST', headers: { 'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json' }, body: JSON.stringify(b) });
                    if (!r.ok) { var m = 'HTTP ' + r.status; try { var e = await r.json();
                            m = e.message || e.error?.message || m } catch (_) {} throw new Error((TYPE_LABELS[node.type] || node.type) + ' ' + node.modelName + ': ' + m); }
                    var j = await r.json();
                    return j.choices?.[0]?.message?.content || '(无回复)';
                }
            case 'image-gen':
                {
                    var prompt = userText || (node.systemPrompt || '一幅美丽的风景画');
                    var b = { model: node.modelId, prompt: prompt, n: 1, size: (node.params?.width || 1024) + 'x' + (node.params?.height || 1024) };
                    if (userImage) b.image = userImage;
                    var r = await fetch(curProv().base_url + '/image/generations', { signal: signal, method: 'POST', headers: { 'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json' }, body: JSON.stringify(b) });
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
                    if (userImages && userImages.length > 0) {
                        for (var ui = 0; ui < userImages.length; ui++) {
                            content.push({ type: 'image_url', image_url: { url: userImages[ui] } });
                        }
                    }
                    var promptText = node.type === 'vision' ? '请分析这张图片' : '请描述这张图片';
                    content.push({ type: 'text', text: userText || promptText });
                    msgs.push({ role: 'user', content: content });
                    var b = { model: node.modelId, messages: msgs, max_tokens: node.params?.max_tokens ?? 1024, temperature: node.params?.temperature ?? 0.5, stream: false };
                    var r = await fetch(curProv().base_url + '/chat/completions', { signal: signal, method: 'POST', headers: { 'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json' }, body: JSON.stringify(b) });
                    if (!r.ok) { var m = 'HTTP ' + r.status; try { var e = await r.json();
                            m = e.message || e.error?.message || m } catch (_) {} throw new Error('图片理解 ' + node.modelName + ': ' + m); }
                    var j = await r.json();
                    return j.choices?.[0]?.message?.content || '(无回复)';
                }
            case 'video-gen':
                {
                    // 硅基流动视频 API
                    var submitBase = curProv().base_url + '/video';
                    var prompt = userText || (node.systemPrompt || '一段动态视频');
                    var submitB = { model: node.modelId, prompt: prompt, image_size: (node.params?.width || 1280) + 'x' + (node.params?.height || 720) };
                    if (userImage) submitB.image = userImage;
                    var subRes = await fetch(submitBase + '/submit', { signal: signal, method: 'POST', headers: { 'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json' }, body: JSON.stringify(submitB) });
                    if (!subRes.ok) { var m = 'HTTP ' + subRes.status; try { var e = await subRes.json(); m = e.message || e.error?.message || m } catch (_) {} throw new Error('视频生成 ' + node.modelName + ': ' + m); }
                    var subData = await subRes.json();
                    // 兼容多种返回格式: requestId / request_id / id / result.id / data.id
                    var reqId = subData.requestId || subData.request_id || subData.id || '';
                    if (!reqId && subData.data) reqId = subData.data.requestId || subData.data.request_id || subData.data.id || subData.data.task_id || '';
                    if (!reqId && subData.result) reqId = subData.result.id || subData.result.request_id || '';
                    if (!reqId) throw new Error('视频生成 ' + node.modelName + ': 未获取到任务ID');
                    // 轮询结果：POST /v1/video/status { requestId }
                    var maxPoll = 120;
                    for (var pollCnt = 0; pollCnt < maxPoll; pollCnt++) {
                        await new Promise(function(r2) { setTimeout(r2, 3000); });
                        if (signal && signal.aborted) throw new Error('aborted');
                        var staRes = await fetch(submitBase + '/status', { signal: signal, method: 'POST', headers: { 'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json' }, body: JSON.stringify({ requestId: reqId }) });
                        if (!staRes.ok) continue;
                        var staData = await staRes.json();
                        var st = (staData.status || '').toLowerCase();
                        var vu = '';
                        if (staData.results) vu = staData.results.video_url || staData.results.url || '';
                        if (st === 'inqueue' || st === 'processing' || st === 'running' || st === 'queued') continue;
                        if (st === 'succeed' || st === 'success' || st === 'completed' || st === 'done') return vu || '(视频生成完成)';
                        if (st === 'failed') throw new Error('视频生成失败: ' + (staData.reason || staData.message || ''));
                        // 有视频 URL 视为完成
                        if (vu) return vu;
                    }
                    throw new Error('视频生成超时');
                }
            case 'video-understand':
                throw new Error('视频理解暂未开放 API 调用');
            case 'tts':
                {
                    var text = (node.systemPrompt || userText || '你好');
                    var customVoice = (node.params && node.params.custom_voice) || '';
                    var ttsVoices = (node.modelId ? getTTSVoices(node.modelId) : ['alex']);
                    var ttsVoice = customVoice || node.params?.voice || ttsVoices[0] || 'alex';
                    if (!customVoice && ttsVoices.indexOf(ttsVoice) < 0) ttsVoice = ttsVoices[0] || 'alex';
                    // 硅基流动 TTS 要求 voice 为 "模型ID:音色名" 格式（如 "CosyVoice2-0.5B:alex"）
                    var fullVoice = (curProv().base_url.indexOf('siliconflow') >= 0 && ttsVoice.indexOf(':') < 0) ? (node.modelId + ':' + ttsVoice) : ttsVoice;
                    var b = { model: node.modelId, input: text, voice: fullVoice, response_format: 'mp3', speed: node.params?.speed || 1.0 };
                    var r = await fetch(curProv().base_url + '/audio/speech', { signal: signal, method: 'POST', headers: { 'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json' }, body: JSON.stringify(b) });
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
                    var r = await fetch(curProv().base_url + '/audio/transcriptions', { signal: signal, method: 'POST', headers: { 'Authorization': 'Bearer ' + key }, body: f });
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

    // ── 工作流资产 ──
    var assets = [];
    var pendingAssets = [];  // 由 executeNode 在执行时直接填充
    var ASSETS_LOCAL_KEY = 'wf_assets_cache';

    function blobToBase64(blob) {
        return new Promise(function(res, rej) {
            var r = new FileReader();
            r.onload = function() { res(r.result); };
            r.onerror = rej;
            r.readAsDataURL(blob);
        });
    }

    function saveAssetsToLocal(ts, data) {
        try {
            var all = JSON.parse(localStorage.getItem(ASSETS_LOCAL_KEY) || '{}');
            // 截断大内容以节省 localStorage 空间
            var trimmed = JSON.parse(JSON.stringify(data));
            trimmed.nodes.forEach(function(n) {
                if (n.contentType !== 'text' && n.content.length > 500) {
                    n.content = n.content.substring(0, 200) + '...[已截断]';
                }
            });
            all[ts] = trimmed;
            localStorage.setItem(ASSETS_LOCAL_KEY, JSON.stringify(all));
        } catch (_) {}
    }

    function loadAssetsFromLocal() {
        try {
            var all = JSON.parse(localStorage.getItem(ASSETS_LOCAL_KEY) || '{}');
            return Object.keys(all).sort().reverse().map(function(k) { return all[k]; });
        } catch (_) { return []; }
    }

    async function saveWorkflowAssets(duration) {
        try {
            console.log('[WF Assets] saveWorkflowAssets called, duration:', duration);
            console.log('[WF Assets] pendingAssets count:', pendingAssets.length, JSON.stringify(pendingAssets.map(function(p){return p.nodeId+':'+p.contentType+':'+(typeof p.content).substring(0,3);})));

            if (!pendingAssets.length) {
                console.warn('[WF Assets] pendingAssets is empty!');
                showToast('ℹ️ 没有捕获到资产数据（pendingAssets 为空）', '');
                return;
            }

            // Step 1: 去重：对于同一个 nodeId 只保留最后一次推入的数据（最新执行结果）
            var seen = {}, assetNodes = [];
            for (var pi = pendingAssets.length - 1; pi >= 0; pi--) {
                var pa = pendingAssets[pi];
                if (!seen[pa.nodeId]) {
                    seen[pa.nodeId] = true;
                    assetNodes.unshift({
                        nodeId: pa.nodeId,
                        type: pa.type,
                        modelName: pa.modelName,
                        category: pa.category,
                        order: assetNodes.length + 1,
                        contentType: pa.contentType || 'text',
                        content: pa.content || ''
                    });
                }
            }

            console.log('[WF Assets] deduped nodes:', assetNodes.length, assetNodes.map(function(n){return n.nodeId+':'+n.contentType}));

            // Step 2: 并发转换 blob → base64（仅对 blob URL）
            var skipCount = 0;
            await Promise.all(assetNodes.map(function(an) {
                if (typeof an.content === 'string' && an.content.indexOf('blob:') === 0) {
                    return fetch(an.content).then(function(r){ return r.blob(); })
                        .then(function(b){ return blobToBase64(b); })
                        .then(function(b64){ an.content = b64; })
                        .catch(function(e){
                            skipCount++;
                            console.warn('[WF Assets] blob转换失败:', an.modelName, e.message);
                            an.content = '[二进制内容]';
                        });
                }
                return Promise.resolve();
            }));

            console.log('[WF Assets] after blob conversion, skipCount:', skipCount, 'final content types:', assetNodes.map(function(n){return n.contentType+':'+(n.content?n.content.substring(0,20):'empty')}));

            // Step 3: 构建请求体
            var now = new Date();
            var pad2 = function(v) { return String(v).padStart(2, '0'); };
            var ts = now.getFullYear() + pad2(now.getMonth() + 1) + pad2(now.getDate()) + '_'
                + pad2(now.getHours()) + pad2(now.getMinutes()) + pad2(now.getSeconds());
            var body = {
                timestamp: ts,
                formattedTime: now.toLocaleString('zh-CN'),
                nodeCount: assetNodes.length,
                duration: duration,
                nodes: assetNodes,
            };

            console.log('[WF Assets] body built, posting to backend...');

            // Step 4: POST 到后端
            var saved = false;
            try {
                var r = await fetch('/api/workflower/save', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body),
                });
                saved = r.ok;
                console.log('[WF Assets] backend response:', r.status, saved ? 'OK' : 'FAIL');
                if (!saved) {
                    var errText = await r.text().catch(function(){return '';});
                    console.warn('[WF Assets] backend error body:', errText);
                }
            } catch (e) {
                console.warn('[WF Assets] backend fetch error:', e.message);
            }

            // Step 5: 保存到本地 (降级)
            if (!saved) {
                saveAssetsToLocal(ts, body);
                showToast('💾 ' + assetNodes.length + '个资产已保存(本地)' + (skipCount ? ',跳过' + skipCount : ''), 'success');
                console.log('[WF Assets] saved to localStorage');
            } else {
                showToast('💾 ' + assetNodes.length + '个资产已保存' + (skipCount ? ',跳过' + skipCount : ''), 'success');
                console.log('[WF Assets] saved to backend');
            }

            // Step 6: 刷新前端面板
            console.log('[WF Assets] calling loadWorkflowAssets (await)...');
            await loadWorkflowAssets();
            console.log('[WF Assets] done');
        } catch (err) {
            console.error('[WF Assets] 保存失败:', err);
            showToast('❌ 资产保存失败: ' + err.message, 'error');
        }
    }

    async function loadWorkflowAssets() {
        console.log('[WF Assets] loadWorkflowAssets called');
        try {
            var r = await fetch('/api/workflower/list');
            console.log('[WF Assets] list fetch status:', r.status);
            if (r.ok) {
                var d = await r.json();
                console.log('[WF Assets] list data count:', (d.assets || []).length);
                assets = d.assets || [];
                renderAssets();
                console.log('[WF Assets] render from backend done');
                return;
            }
            console.warn('[WF Assets] list fetch not ok:', r.status);
        } catch (e) {
            console.warn('[WF Assets] list fetch error:', e.message);
        }
        // 降级到 localStorage
        console.log('[WF Assets] falling back to localStorage');
        assets = loadAssetsFromLocal();
        renderAssets();
        console.log('[WF Assets] render from localStorage done');
    }

    function renderAssets() {
        try {
        console.log('[WF Assets] renderAssets called, assets count:', assets ? assets.length : 0);
        var el = $('wfAssetsContainer');
        if (!el) { console.warn('[WF Assets] wfAssetsContainer not found!'); return; }
        if (!assets || !assets.length) {
            el.innerHTML = '<div class="wf-no-models">运行工作流后自动保存资产</div>';
            return;
        }
        var html = '';
        for (var ai = 0; ai < Math.min(assets.length, 30); ai++) {
            var a = assets[ai];
            var nodes = a.nodes || [];
            var outputCount = 0, monitorCount = 0;
            nodes.forEach(function(n) { if (n.category === 'output') outputCount++; else monitorCount++; });

            html += '<div class="wf-asset-item">'
                + '<div class="wf-asset-header" data-ai="' + ai + '">'
                + '<span class="wf-asset-time">' + escapeHtml(a.formattedTime || a.timestamp || '') + '</span>'
                + '<span class="wf-asset-badge">' + a.nodeCount + '节点</span>'
                + '<span class="wf-asset-dur">' + escapeHtml(a.duration || '') + '</span>'
                + '</div>'
                + '<div class="wf-asset-body" id="wfAssetBody_' + ai + '">';
            for (var ni = 0; ni < nodes.length; ni++) {
                var nd = nodes[ni];
                var icon = nd.category === 'output' ? '🖥️' : '📊';
                var label = nd.category === 'output' ? '最终输出 #' : '数据流转 #';
                var preview = '';
                if (nd.contentType === 'text' && nd.content) {
                    var txt = nd.content;
                    if (txt.length > 80) txt = txt.substring(0, 80) + '…';
                    preview = '<div class="wf-asset-preview-text">' + escapeHtml(txt) + '</div>';
                } else if (nd.contentType === 'image' && nd.content) {
                    preview = '<img src="' + nd.content + '" class="wf-asset-preview-img" />';
                } else if (nd.contentType === 'audio' && nd.content) {
                    preview = '<audio controls src="' + nd.content + '" style="width:100%;height:28px;"></audio>';
                } else if (nd.contentType === 'video' && nd.content) {
                    preview = '<video controls src="' + nd.content + '" style="max-width:100%;max-height:80px;"></video>';
                } else if (!nd.content && nd.contentType !== 'text') {
                    preview = '<span style="color:#888;font-size:10px;">💾 保存到文件夹可查看文件</span>';
                }
                html += '<div class="wf-asset-node' + (nd.contentType !== 'text' ? ' wf-asset-node-clickable' : '') + '" data-ts="' + escapeHtml(a.timestamp) + '" data-node-id="' + escapeHtml(nd.nodeId || '') + '" data-ctype="' + nd.contentType + '">'
                    + '<div class="wf-asset-node-info">' + icon + ' ' + label + nd.order
                    + ' <span class="wf-asset-type-tag">' + nd.contentType + '</span></div>'
                    + '<div class="wf-asset-node-summary">' + preview + '</div>'
                    + '<div class="wf-asset-node-player" style="display:none;"></div>'
                    + '</div>';
            }
            html += '</div>'
                + '<div class="wf-asset-actions">'
                + '<button class="wf-asset-save-btn" data-ts="' + escapeHtml(a.timestamp) + '">💾 保存到文件夹</button>'
                + '</div>'
                + '</div>';
        }
        if (assets.length > 30) {
            html += '<div style="padding:6px 10px;color:#888;font-size:11px;">仅显示最近 30 条资产</div>';
        }
        el.innerHTML = html;

        // 展开/折叠
        el.querySelectorAll('.wf-asset-header').forEach(function(h) {
            h.addEventListener('click', function() {
                var body = document.getElementById('wfAssetBody_' + h.dataset.ai);
                if (body) body.classList.toggle('open');
                h.classList.toggle('open');
            });
        });
        // 保存按钮
        el.querySelectorAll('.wf-asset-save-btn').forEach(function(btn) {
            btn.addEventListener('click', function(e) {
                e.stopPropagation();
                exportAssetFiles(btn.dataset.ts);
            });
        });
        // 节点点击预览
        el.querySelectorAll('.wf-asset-node-clickable').forEach(function(nodeEl) {
            nodeEl.addEventListener('click', function(e) {
                if (e.target.closest('.wf-asset-save-btn')) return;
                var playerDiv = nodeEl.querySelector('.wf-asset-node-player');
                if (!playerDiv) return;

                // 已展开 → 收起
                if (playerDiv.style.display === '') {
                    playerDiv.style.display = 'none';
                    return;
                }

                // 已加载过 → 直接展示
                if (playerDiv._loaded) {
                    playerDiv.style.display = '';
                    return;
                }

                // 首次加载 → 从后端获取
                var ts = nodeEl.dataset.ts, nid = nodeEl.dataset.nodeId, ct = nodeEl.dataset.ctype;
                if (!ts || !nid) return;
                playerDiv.innerHTML = '<span style="color:#888;font-size:10px;">⏳ 加载中...</span>';
                playerDiv.style.display = '';
                fetch('/api/workflower/' + ts).then(function(r) { return r.json(); }).then(function(data) {
                    var nd = (data.nodes || []).find(function(n) { return n.nodeId === nid; });
                    if (!nd || !nd.content) { playerDiv.innerHTML = '<span style="color:#f88;font-size:10px;">❌ 内容不可用</span>'; return; }
                    var h = '';
                    if (ct === 'audio') h = '<audio controls src="' + nd.content + '" style="width:100%;height:32px;"></audio>';
                    else if (ct === 'image') h = '<img src="' + nd.content + '" style="max-width:100%;max-height:160px;border-radius:4px;display:block;" />';
                    else if (ct === 'video') h = '<video controls src="' + nd.content + '" style="max-width:100%;max-height:120px;border-radius:4px;"></video>';
                    else h = '<span style="color:#888;font-size:10px;">无法预览</span>';
                    playerDiv.innerHTML = h;
                    playerDiv._loaded = true;
                }).catch(function() {
                    playerDiv.innerHTML = '<span style="color:#f88;font-size:10px;">❌ 加载失败</span>';
                });
            });
        });
        // 默认展开第一个
        var firstBody = document.getElementById('wfAssetBody_0');
        if (firstBody) { firstBody.classList.add('open');
            var firstH = el.querySelector('.wf-asset-header');
            if (firstH) firstH.classList.add('open'); }
        console.log('[WF Assets] renderAssets completed, html length:', html.length);
        } catch (err) {
            console.error('[WF Assets] renderAssets error:', err);
        }
    }

    async function exportAssetFiles(assetTimestamp) {
        if (!assetTimestamp) { showToast('资产时间戳缺失', 'error'); return; }
        // 获取资产数据
        var assetData = null;
        try {
            var r = await fetch('/api/workflower/' + assetTimestamp);
            if (r.ok) assetData = await r.json();
        } catch (_) {}
        if (!assetData) {
            // 尝试从 localStorage 获取
            try {
                var all = JSON.parse(localStorage.getItem(ASSETS_LOCAL_KEY) || '{}');
                assetData = all[assetTimestamp] || null;
            } catch (_) {}
        }
        if (!assetData || !assetData.nodes || !assetData.nodes.length) {
            showToast('未找到资产数据', 'error');
            return;
        }

        // 选择目标文件夹
        var dirHandle = null;
        try {
            dirHandle = await window.showDirectoryPicker();
        } catch (err) {
            if (err.name === 'AbortError') return;
            showToast('文件夹选择失败', 'error');
            return;
        }

        var savedCount = 0;
        for (var i = 0; i < assetData.nodes.length; i++) {
            var nd = assetData.nodes[i];
            if (!nd.content && nd.contentType === 'text') continue;
            var extMap = { text: '.txt', image: '.png', audio: '.mp3', video: '.mp4' };
            var ext = extMap[nd.contentType] || '.dat';
            var prefix = nd.category === 'output' ? 'output' : 'monitor';
            var fname = prefix + '_' + nd.order + ext;

            try {
                var fh = await dirHandle.getFileHandle(fname, { create: true });
                var w = await fh.createWritable();
                if (nd.contentType === 'text') {
                    await w.write(nd.content || '');
                } else if (nd.content && nd.content.indexOf('data:') === 0) {
                    var resp2 = await fetch(nd.content);
                    var blob2 = await resp2.blob();
                    await w.write(blob2);
                }
                await w.close();
                savedCount++;
            } catch (err) {
                showToast('保存 ' + fname + ' 失败: ' + err.message, 'error');
            }
        }
        showToast('✅ 已保存 ' + savedCount + ' 个文件到 ' + dirHandle.name, 'success');
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
        var startTime = Date.now();
        pendingAssets = [];  // 清空上次运行残留

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
                            card.classList.add('executed'); } } catch (err) { if (stopRequested || (err.message && err.message.indexOf('aborted') >= 0)) break;
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
                                bCard.classList.add('executed'); } } catch (err) { if (stopRequested || (err.message && err.message.indexOf('aborted') >= 0)) break;
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
                    card.classList.add('executed'); } } catch (err) { if (err.name === 'AbortError' || (err.message && err.message.indexOf('aborted') >= 0)) { if (stopRequested) { showToast('⏹ 已停止', ''); break; } else { continue; } } hasError = true; if (card) { card.classList.remove('executing');
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
        if (!hasError && !stopRequested) {
            showToast('✅ 工作流执行完成！', 'success');
            // 自动保存资产（异步，不影响主流程）
            var dur = ((Date.now() - startTime) / 1000).toFixed(1) + 's';
            saveWorkflowAssets(dur);
        }
        renderAll();
    }

    // ── 侧边栏按钮绑定（放置模式） ──
    container.querySelectorAll('.wf-media-btn').forEach(function(b) {
        b.addEventListener('click', function() {
            if (b.id === 'wfAddMonitorBtn') { startPlacement('data-monitor', null); return; }
            if (b.id === 'wfAddExportBtn') { startPlacement('data-export', null); return; }
            startPlacement('media-' + b.dataset.media, null);
        });
    });
    container.querySelectorAll('.wf-output-btn').forEach(function(b) {
        b.addEventListener('click', function() { startPlacement('output-' + b.dataset.output, null); });
    });
    $('wfAddLoopStartBtn').addEventListener('click', function() { startPlacement('loop-start', null); });
    $('wfAddLoopEndBtn').addEventListener('click', function() { startPlacement('loop-end', null); });

    // ── API Key & 模型加载 ──
    apiKeyInput.value = apiKey;
    apiKeyInput.placeholder = '输入 ' + curProv().name + ' API Key ...';
    apiKeyInput.addEventListener('input', function() { apiKey = apiKeyInput.value.trim();
        localStorage.setItem(curProv().api_key_storage, apiKey); });

    // ── 提供商切换 ──
    $('wfProviderSelect').value = selectedProvider;
    $('wfProviderSelect').addEventListener('change', function() {
        // 保存当前 key
        localStorage.setItem(curProv().api_key_storage, apiKey);
        selectedProvider = this.value;
        localStorage.setItem('wf_selected_provider', selectedProvider);
        // 更新 UI
        apiKey = localStorage.getItem(curProv().api_key_storage) || '';
        apiKeyInput.value = apiKey;
        apiKeyInput.placeholder = '输入 ' + curProv().name + ' API Key ...';
        // 切换后清除并尝试加载缓存
        fetchedModels = [];
        var cached = loadCachedModels();
        if (cached && cached.length) {
            fetchedModels = cached;
            apiStatus.textContent = '📦 从缓存加载了 ' + cached.length + ' 个模型 (' + curProv().name + ')';
            apiStatus.className = 'wf-api-status success';
        } else {
            apiStatus.textContent = '已切换到 ' + curProv().name + '，输入 API Key 后加载模型';
            apiStatus.className = 'wf-api-status';
        }
        renderSidebarModels();
    });

    async function loadModels() {
        var key = apiKeyInput.value.trim();
        if (!key) { apiStatus.textContent = '⚠️ 请先输入 API Key';
            apiStatus.className = 'wf-api-status error'; return; }
        apiKey = key;
        localStorage.setItem(curProv().api_key_storage, key);
        var cached = loadCachedModels();
        if (cached && cached.length) { fetchedModels = cached;
            renderSidebarModels();
            collapseModelPlaza();
            apiStatus.textContent = '📦 从缓存加载了 ' + cached.length + ' 个模型';
            apiStatus.className = 'wf-api-status success'; }
        loadModelsBtn.disabled = true;
        apiStatus.textContent = '⏳ 正在从 ' + curProv().name + ' 获取模型列表...';
        apiStatus.className = 'wf-api-status loading';
        try {
            var fresh = await fetchModelsFromAPI(key);
            if (fresh && fresh.length) { fetchedModels = fresh;
                renderSidebarModels();
                collapseModelPlaza();
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
        localStorage.removeItem(curProv().model_cache);
        localStorage.removeItem(curProv().cache_time);
        fetchedModels = [];
        renderSidebarModels();
        apiStatus.textContent = '已清除模型缓存';
        apiStatus.className = 'wf-api-status';
        showToast('缓存已清除', '');
    });

    // ── 工作流管理 ──
    function serializeWorkflow() { saveCurrentWs(); return JSON.stringify({ version: '1.0', workspaces: workspaces }, null, 2); }

    function clearStaleBlobUrls() {
        nodes.forEach(function(n) {
            if (n.savedContent && typeof n.savedContent === 'string' && n.savedContent.indexOf('blob:') === 0) {
                n.savedContent = null;
                n.savedContentType = null;
            }
        });
    }

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
            clearStaleBlobUrls();
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

    // ── 侧边栏模块折叠 ──
    var _sectionCollapsed = {};

    function initSidebarCollapse() {
        var mainView = $('wfSidebarMainView');
        if (!mainView) return;

        var cats = mainView.querySelectorAll('.wf-category');
        cats.forEach(function(cat) {
            // 为该分类添加 ▶/▼ 指示器
            var text = cat.textContent.replace(/▶|▼/g, '').trim();
            var key = text.replace(/[^a-zA-Z0-9一-鿿]/g, '');
            if (cat.id === 'wfModelPlazaTitle') key = 'modelPlaza';
            cat.setAttribute('data-section-key', key);
            cat.style.cursor = 'pointer';
            cat.style.userSelect = 'none';

            // 收集该分类之后、下一个分类之前的所有兄弟元素
            var contentEls = [];
            var next = cat.nextElementSibling;
            while (next && !next.classList.contains('wf-category')) {
                contentEls.push(next);
                next = next.nextElementSibling;
            }
            if (!contentEls.length) return;

            // 包裹到 content div 中
            var wrapper = document.createElement('div');
            wrapper.className = 'wf-section-content';
            contentEls.forEach(function(el) { wrapper.appendChild(el); });
            cat.parentNode.insertBefore(wrapper, cat.nextSibling);

            // 初始化状态：默认展开，模型广场默认折叠
            if (_sectionCollapsed[key] === undefined) {
                _sectionCollapsed[key] = (key === 'modelPlaza' || key.indexOf('工作流管理') >= 0);
            }
            updateSectionState(cat, key, wrapper);

            cat.addEventListener('click', function(e) {
                if (e.target.closest('input,select,button,.wf-model-btn,.wf-cat-toggle')) return;
                _sectionCollapsed[key] = !_sectionCollapsed[key];
                updateSectionState(cat, key, wrapper);
            });
        });
    }

    function updateSectionState(cat, key, wrapper) {
        var collapsed = _sectionCollapsed[key];
        // 更新指示器
        var txt = cat.textContent.replace(/▶|▼/g, '').trim();
        cat.textContent = (collapsed ? '▶' : '▼') + ' ' + txt;
        wrapper.style.display = collapsed ? 'none' : '';
        // 同步更新 collapsedCats（保持已有的模型广场折叠逻辑兼容）
        if (key === 'modelPlaza') {
            // 模型广场内部的分类（图片、对话等）也初始化
        }
    }

    // 在模型加载后强制折叠模型广场
    function collapseModelPlaza() {
        _sectionCollapsed['modelPlaza'] = true;
        var cat = document.querySelector('#wfSidebarMainView .wf-category[data-section-key="modelPlaza"]');
        if (cat) {
            var wrapper = cat.nextElementSibling;
            if (wrapper && wrapper.classList.contains('wf-section-content')) {
                updateSectionState(cat, 'modelPlaza', wrapper);
            }
        }
    }

    var autoSaveToggle = $('wfAutoSaveToggle');
    autoSaveToggle.addEventListener('click', function() {
        autoSaveEnabled = !autoSaveEnabled;
        autoSaveToggle.textContent = autoSaveEnabled ? '⏸ 自动保存: 开' : '▶️ 自动保存: 关';
        showToast(autoSaveEnabled ? '自动保存已开启' : '自动保存已关闭', '');
    });
    // ── 侧边栏视图切换（主视图 / 资产视图） ──
    var assetsBtn = $('wfAssetsBtn');
    var assetsBackBtn = $('wfAssetsBackBtn');
    var sidebarMainView = $('wfSidebarMainView');
    var sidebarAssetsView = $('wfSidebarAssetsView');

    function showSidebarView(view) {
        if (!sidebarMainView || !sidebarAssetsView) return;
        if (view === 'assets') {
            sidebarMainView.style.display = 'none';
            sidebarAssetsView.style.display = '';
        } else {
            sidebarMainView.style.display = '';
            sidebarAssetsView.style.display = 'none';
        }
    }

    if (assetsBtn) {
        assetsBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            showSidebarView('assets');
            loadWorkflowAssets();  // 进入时刷新
        });
    }
    if (assetsBackBtn) {
        assetsBackBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            showSidebarView('main');
        });
    }

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
    // 使用 onclick 而非 addEventListener，避免与 runWorkflow 内部的 onclick 管理冲突导致双重触发
    $('wfRunWorkflowBtn').onclick = runWorkflow;

    // ── 画布交互 ──
    canvasContainer.addEventListener('click', function(e) {
        // 如果刚完成拖拽平移，忽略此次 click
        if (panState.moved) { panState.moved = false; return; }
        // 节点放置模式：单击画布任意位置放置
        if (placeState) {
            if (e.target.closest('.wf-sidebar, .wf-floating-actions, .wf-tab-bar, .wf-action-btn')) return;
            var r = canvasContainer.getBoundingClientRect();
            placeNodeAt((e.clientX - r.left - canvasPan.x) / canvasZoom, (e.clientY - r.top - canvasPan.y) / canvasZoom);
            return;
        }
        if (e.target.classList.contains('wf-conn-line') && e.target.dataset.connIdx !== undefined) {
            var idx = parseInt(e.target.dataset.connIdx);
            if (!isNaN(idx) && idx >= 0 && idx < connections.length) { connections.splice(idx, 1);
                renderAll();
                scheduleAutoSave(); return; }
        }
        if (e.target === canvasContainer || e.target.id === 'wfNodesLayer' || e.target.id === 'wfLineLayer' || e.target === canvasViewport) {
            selectedNodeId = null;
            container.querySelectorAll('.wf-node-card.selected').forEach(function(c) {
                c.classList.remove('selected');
            });
        }
    });
    canvasContainer.addEventListener('wheel', function(e) {
        e.preventDefault();
        var r = canvasContainer.getBoundingClientRect();
        zoomCanvas(e.deltaY > 0 ? 0.9 : 1.1, e.clientX, e.clientY);
    }, { passive: false });
    var panState = { active: false, sx: 0, sy: 0, px: 0, py: 0, moved: false, byButton: -1 };
    var PAN_THRESHOLD = 4; // 像素移动阈值

    function startPan(e, btn) {
        // 仅在画布空白区域（不在节点、端口、连线上）
        if (e.target.closest('.wf-node-card, .wf-port, .wf-conn-line, .wf-floating-actions, .wf-tab-bar')) return;
        panState = { active: true, sx: e.clientX, sy: e.clientY, px: canvasPan.x, py: canvasPan.y, moved: false, byButton: btn };
        e.preventDefault();
    }

    function updatePan(e) {
        if (!panState.active) return;
        var dx = e.clientX - panState.sx;
        var dy = e.clientY - panState.sy;
        if (!panState.moved && (dx * dx + dy * dy) > PAN_THRESHOLD * PAN_THRESHOLD) {
            panState.moved = true;
            canvasContainer.style.cursor = 'grabbing';
        }
        if (panState.moved) {
            canvasPan.x = panState.px + dx;
            canvasPan.y = panState.py + dy;
            applyCanvasTransform();
        }
    }

    function endPan(e) {
        if (panState.active && panState.byButton === e.button) {
            panState.active = false;
            canvasContainer.style.cursor = '';
        }
    }

    canvasContainer.addEventListener('mousedown', function(e) {
        if (e.button === 0) startPan(e, 0);   // 左键
        if (e.button === 1) { startPan(e, 1); return; } // 中键（阻止默认滚动）
    });
    window.addEventListener('mousemove', updatePan);
    window.addEventListener('mouseup', endPan);

    // 幽灵节点跟随鼠标
    canvasContainer.addEventListener('mousemove', function(e) {
        if (!placeState || !placeState.ghostEl) return;
        var r = canvasContainer.getBoundingClientRect();
        var x = (e.clientX - r.left - canvasPan.x) / canvasZoom;
        var y = (e.clientY - r.top - canvasPan.y) / canvasZoom;
        placeState.ghostEl.style.left = Math.round(x) + 'px';
        placeState.ghostEl.style.top = Math.round(y) + 'px';
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
        if (e.key === 'Escape') {
            if (placeState) { cancelPlacement(); showToast('已取消放置', ''); return; }
            selectedNodeId = null;
            container.querySelectorAll('.wf-node-card.selected').forEach(function(c) {
                c.classList.remove('selected');
            });
        }
    };
    document.addEventListener('keydown', _keyHandler);

    // ── 初始化 ──
    $('wfModelSearchInput')?.addEventListener('input', function() { renderSidebarModels(); });

    var cached = loadCachedModels();
    if (cached && cached.length) { fetchedModels = cached;
        renderSidebarModels();
        collapseModelPlaza();
        apiStatus.textContent = '📦 已加载 ' + cached.length + ' 个模型 (缓存)';
        apiStatus.className = 'wf-api-status success'; } else renderSidebarModels();

    tryAutoRestore();
    initSidebarCollapse();
    loadWorkflowAssets();
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
