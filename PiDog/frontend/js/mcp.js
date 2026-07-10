/* ============================================================
   mcp.js — MCP 服务器管理页面
   功能：本地 MCP 启停 + 魔搭 MCP 广场浏览/搜索/添加
   ============================================================ */

async function renderMcpPage(container) {
    async function loadList() {
        try { return await api.getMcpList(); } catch (e) { return []; }
    }
    async function loadMsStatus() {
        try { return await api.modelscopeGetStatus(); } catch (e) { return null; }
    }
    async function searchMs(search, category, page) {
        const validPage = Math.max(1, parseInt(page) || 1);
        try { return await api.modelscopeSearch(search, category, validPage); } catch (e) { return null; }
    }
    async function loadCategories() {
        try {
            const r = await api.modelscopeCategories();
            return Array.isArray(r) ? r : [];
        } catch (e) { return []; }
    }

    let mcps = await loadList();
    let msStatus = await loadMsStatus();

    // 魔搭搜索状态
    let searchKeyword = '';
    let activeCategory = '';
    let currentPage = 1;
    let searchResult = null;        // 搜索结果缓存
    let hotLoaded = false;
    let searchLoading = false;
    let categories = ['热门'];      // 默认加上"热门"
    let loadedCategories = false;

    // ---- 首次加载热门 MCP ----
    async function loadHotMcps() {
        if (hotLoaded) return;
        hotLoaded = true;
        searchLoading = true;
        render();
        const r = await searchMs('', '', 1);
        if (r && r.success) {
            searchResult = r;
            // 从结果中提取分类
            if (!loadedCategories) {
                const cats = await loadCategories();
                if (cats.length > 0) {
                    categories = ['全部', ...cats];
                }
                loadedCategories = true;
            }
        }
        searchLoading = false;
        // 如果 mcps 为空，可能是启动阶段 API 未就绪，重试一次
        if (mcps.length === 0) { mcps = await loadList(); msStatus = await loadMsStatus(); }
        render();
    }

    // ---- 执行搜索 ----
    async function doSearch() {
        // 从输入框读取当前搜索关键字
        const input = document.getElementById('ms-search-input');
        if (input) searchKeyword = input.value.trim();
        searchLoading = true;
        currentPage = 1;
        render();
        const cat = activeCategory === '全部' || activeCategory === '热门' ? '' : activeCategory;
        const r = await searchMs(searchKeyword, cat, 1);
        if (r) searchResult = r;
        searchLoading = false;
        render();
    }

    loadHotMcps();

    // ==================== 渲染 ====================

    function render() {
        console.log("[MCP] raw[0]=", JSON.stringify(mcps[0])); console.log("[MCP] types=", mcps.map(m=>m.type), "mcps=", mcps.length, "local=", mcps.filter(m => m.type === "local").length, "remote=", mcps.filter(m => m.type === "modelscope_remote").length);
        const localMcps = mcps.filter(m => m.type === 'local');
        const hubMcp = mcps.find(m => m.type === 'hub');
        const msRemotes = mcps.filter(m => m.type === 'modelscope_remote');
        const allLocalCards = [
            ...localMcps.map(m => renderLocalCard(m)),
            ...msRemotes.map(m => renderMsRemoteCard(m)),
        ].join('');
        const hubCard = hubMcp ? renderHubCard(hubMcp, msRemotes) : '';

        // 已连接的魔搭服务名集合（支持完整 ID 匹配）
        const _connectedNames = msRemotes.map(r => (r.ms_name || '').toLowerCase());
        const connectedMsNames = new Set(_connectedNames);
        function isConnected(serverId) {
            if (!serverId) return false;
            if (connectedMsNames.has(serverId.toLowerCase())) return true;
            // 也匹配 ID 的最后一段（如 @modelcontextprotocol/fetch → fetch）
            const last = serverId.split('/').pop().toLowerCase();
            return connectedMsNames.has(last);
        }

        // ---- 搜索结果渲染 ----
        const servers = searchResult?.servers ?? [];
        const total = searchResult?.total ?? 0;
        const hasSearched = searchResult !== null;

        const serverCards = servers.length > 0 ? servers.map(s => {
            const connected = isConnected(s.id);
            const catTags = (s.categories || []).map(c =>
                `<span class="badge badge-purple" style="font-size:10px;">${escapeHtml(c)}</span>`
            ).join(' ');

            return `
                <div class="card" style="padding:14px;display:flex;flex-direction:column;gap:8px;border-color:${connected ? 'var(--green)' : 'var(--border)'};">
                    <div class="flex-between">
                        <div style="flex:1;min-width:0;">
                            <span style="font-weight:600;font-size:14px;color:var(--accent);">${escapeHtml(s.name || s.raw_name || s.id)}</span>
                            <span class="mono" style="color:var(--text-dim);font-size:10px;margin-left:6px;display:inline-block;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;vertical-align:middle;">${escapeHtml(s.id)}</span>
                        </div>
                        ${connected
                            ? '<span class="badge badge-green">已连接</span>'
                            : `<button class="btn btn-xs btn-primary" data-ms-deploy="${escapeHtml(s.id)}" data-ms-name="${escapeHtml(s.name || s.raw_name || s.id)}">⚡ 一键连接</button>`
                        }
                    </div>
                    <div style="font-size:12px;color:var(--text-dim);line-height:1.5;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;">
                        ${escapeHtml(s.description || '暂无描述')}
                    </div>
                    <div class="flex-between" style="font-size:11px;color:var(--text-dim);">
                        <span>👤 ${escapeHtml(s.publisher || '未知')}</span>
                        <span>👁️ ${fmt(s.view_count || 0)}</span>
                        ${s.is_verified ? '<span class="badge badge-green" style="font-size:10px;">✅ 已验证</span>' : ''}
                    </div>
                    <div style="display:flex;gap:4px;flex-wrap:wrap;">${catTags}</div>
                </div>
            `;
        }).join('') : '';

        // ---- 组合页面 ----
        container.innerHTML = `
            <div class="flex-between mb-16">
                <h2 style="margin:0;">🔌 MCP 服务器 <span style="color:var(--text-dim);font-size:13px;">（${mcps.length} 个）</span></h2>
                <button class="btn btn-primary" id="mcp-add-btn">➕ 添加本地 MCP</button>
            </div>

            <!-- ============ 本地 MCP ============ -->
            <h3 style="margin:24px 0 12px;color:var(--text);font-size:15px;font-weight:600;">
                🖥️ 本地 MCP 服务器
                ${msRemotes.length > 0 ? `<span style="color:var(--text-dim);font-weight:400;font-size:13px;">（含 ${msRemotes.length} 个魔搭连接）</span>` : ''}
            </h3>
            ${allLocalCards || '<div class="card" style="text-align:center;padding:20px;color:var(--text-dim);">暂无本地 MCP</div>'}

            <!-- ============ 魔搭 MCP 广场 ============ -->
            <div class="flex-between" style="margin:32px 0 12px;">
                <h3 style="margin:0;color:var(--text);font-size:15px;font-weight:600;">
                    🌐 魔搭 MCP 广场
                    <span style="color:var(--text-dim);font-weight:400;font-size:13px;">
                        ${total > 0 ? `（搜索到 ${total} 个托管服务）` : '（9,200+ 托管服务）'}
                    </span>
                </h3>
                <button class="btn btn-sm" id="ms-help-btn" title="使用帮助" style="font-size:16px;border-radius:50%;width:32px;height:32px;padding:0;">❓</button>
            </div>
            ${hubCard || renderFallbackHubCard()}

            <!-- ============ MCP 搜索/浏览 ============ -->
            <div class="card" style="margin-top:16px;">
                <div class="flex-between mb-12">
                    <span style="font-weight:600;font-size:14px;">🔍 搜索 MCP 服务</span>
                    <span style="font-size:12px;color:var(--text-dim);">
                        ${searchLoading ? '<span class="spinner"></span> 搜索中...' : `共 ${total} 个结果`}
                    </span>
                </div>

                <!-- 搜索栏 -->
                <div style="display:flex;gap:8px;margin-bottom:12px;">
                    <input class="input input-sm" id="ms-search-input" type="text"
                        placeholder="搜索 MCP 服务名称、描述或作者..." style="flex:1;"
                        value="${escapeHtml(searchKeyword)}">
                    <button class="btn btn-sm btn-primary" id="ms-search-btn">🔍 搜索</button>
                    <button class="btn btn-sm" id="ms-search-clear" ${searchKeyword ? '' : 'style="display:none;"'}>✕ 清除</button>
                </div>

                <!-- 分类标签 -->
                <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px;">
                    ${categories.map(tag =>
                        `<button class="btn btn-sm ${activeCategory === tag ? 'btn-primary' : ''}" data-ms-cat="${escapeHtml(tag)}">${escapeHtml(tag)}</button>`
                    ).join('')}
                </div>

                <!-- MCP 服务网格 -->
                ${searchLoading
                    ? '<div style="text-align:center;padding:40px;color:var(--text-dim);"><span class="spinner"></span> 正在搜索魔搭 MCP 广场...</div>'
                    : servers.length > 0
                        ? `<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:8px;">${serverCards}</div>
                           ${total > 20 ? renderPagination(total) : ''}`
                        : hasSearched
                            ? '<div style="text-align:center;padding:30px;color:var(--text-dim);">未找到匹配的 MCP 服务，试试其他关键词</div>'
                            : '<div style="text-align:center;padding:30px;color:var(--text-dim);"><span class="spinner"></span> 正在加载热门 MCP 服务...</div>'
                }
            </div>

        `;

        // ---- 事件绑定 ----
        document.getElementById('mcp-add-btn')?.addEventListener('click', showAddLocalDialog);
        bindLocalCardEvents();
        bindHubCardEvents();
        bindMsCardEvents();
        bindSearchEvents();
        bindHelpButton();
    }

    // ==================== 翻页 ====================

    function renderPagination(total) {
        const totalPages = Math.ceil(total / 20);
        return `
            <div style="display:flex;justify-content:center;align-items:center;gap:8px;margin-top:16px;">
                <button class="btn btn-sm" data-page="${currentPage - 1}" ${currentPage <= 1 ? 'disabled' : ''}>‹ 上一页</button>
                <span style="font-size:13px;color:var(--text-dim);">第 ${currentPage} / ${totalPages} 页</span>
                <button class="btn btn-sm" data-page="${currentPage + 1}" ${currentPage >= totalPages ? 'disabled' : ''}>下一页 ›</button>
            </div>
        `;
    }

    // ==================== 本地 MCP ====================

    function renderLocalCard(m) {
        const statusBadge = m.running
            ? '<span class="badge badge-green">运行中</span>'
            : '<span class="badge badge-red">已停止</span>';
        const enabledBadge = m.enabled
            ? '<span class="badge badge-green">已启用</span>'
            : '<span class="badge badge-yellow">已禁用</span>';
        return `
            <div class="card" style="margin-bottom:12px;">
                <div class="flex-between mb-8">
                    <div>
                        <span style="font-weight:600;font-size:15px;color:var(--accent);">${escapeHtml(m.name)}</span>
                        <span class="mono" style="color:var(--text-dim);margin-left:8px;font-size:12px;">${escapeHtml(m.key)}</span>
                    </div>
                    <div style="display:flex;gap:6px;">${statusBadge} ${enabledBadge}</div>
                </div>
                <div style="font-size:13px;color:var(--text-dim);margin-bottom:12px;">${escapeHtml(m.description)}</div>
                <div class="flex-between" style="font-size:12px;color:var(--text-dim);margin-bottom:12px;">
                    <span>端口：<span class="mono" style="color:var(--text);">${m.port}</span></span>
                    <span>自动启动：${m.auto_start ? '✅ 是' : '❌ 否'}</span>
                </div>
                <div style="display:flex;gap:6px;flex-wrap:wrap;">
                    ${m.running
                        ? `<button class="btn btn-sm btn-danger" data-action="stop" data-key="${m.key}">⏹ 停止</button>`
                        : `<button class="btn btn-sm btn-primary" data-action="start" data-key="${m.key}" ${m.enabled ? '' : 'disabled'}>▶️ 启动</button>`
                    }
                    ${m.enabled
                        ? `<button class="btn btn-sm" data-action="disable" data-key="${m.key}">🚫 禁用</button>`
                        : `<button class="btn btn-sm btn-primary" data-action="enable" data-key="${m.key}">✅ 启用</button>`
                    }
                    <button class="btn btn-sm ${m.auto_start ? 'btn-primary' : ''}" data-action="auto_start" data-key="${m.key}">
                        🔄 自动启动${m.auto_start ? ' ✅' : ''}
                    </button>
                    <button class="btn btn-sm btn-danger" data-action="delete" data-key="${m.key}" style="margin-left:auto;">🗑 删除</button>
                </div>
                <div class="mcp-msg" style="margin-top:8px;font-size:12px;"></div>
            </div>
        `;
    }

    function bindLocalCardEvents() {
        document.querySelectorAll('[data-action]').forEach(btn => {
            btn.addEventListener('click', async function () {
                const action = this.dataset.action;
                const key = this.dataset.key;
                const card = this.closest('.card');
                const msgEl = card?.querySelector('.mcp-msg');
                if (action === 'delete' && !confirm(`确定删除 MCP "${key}" 吗？`)) return;
                this.textContent = '⏳'; this.disabled = true;
                try {
                    const r = await api.operateMcp(key, action);
                    if (r.ok) { mcps = await loadList(); render(); }
                    else {
                        if (msgEl) { msgEl.style.color = 'var(--red)'; msgEl.textContent = '❌ ' + (r.error || ''); }
                        this.textContent = action; this.disabled = false;
                    }
                } catch (e) {
                    if (msgEl) { msgEl.style.color = 'var(--red)'; msgEl.textContent = '❌ ' + escapeHtml(e.message); }
                    this.textContent = '失败'; this.disabled = false;
                }
            });
        });
    }

    function showAddLocalDialog() {
        const html = `
            <h3 style="margin-bottom:16px;">➕ 添加本地 MCP 服务器</h3>
            <div style="margin-bottom:12px;"><label style="display:block;font-size:13px;color:var(--text-dim);margin-bottom:4px;">标识符 (key)</label>
                <input class="input" id="mcp-new-key" placeholder="例如: my_custom_mcp"></div>
            <div style="margin-bottom:12px;"><label style="display:block;font-size:13px;color:var(--text-dim);margin-bottom:4px;">显示名称</label>
                <input class="input" id="mcp-new-name" placeholder="例如: 我的自定义 MCP"></div>
            <div style="margin-bottom:12px;"><label style="display:block;font-size:13px;color:var(--text-dim);margin-bottom:4px;">功能描述</label>
                <textarea class="textarea" id="mcp-new-desc" rows="3" placeholder="描述此 MCP 服务器的功能..."></textarea></div>`;
        showModal(html, true);
        const confirmBtn = document.getElementById('modal-confirm');
        confirmBtn.textContent = '添加';
        confirmBtn.onclick = async function () {
            const key = document.getElementById('mcp-new-key').value.trim();
            const name = document.getElementById('mcp-new-name').value.trim();
            const desc = document.getElementById('mcp-new-desc').value.trim();
            if (!key) { alert('标识符不能为空'); return; }
            this.textContent = '⏳'; this.disabled = true;
            try {
                const r = await api.addMcp(key, name || key, desc);
                if (r.ok) { closeModal(); mcps = await loadList(); render(); }
                else { alert('添加失败: ' + (r.error || '')); this.textContent = '添加'; this.disabled = false; }
            } catch (e) { alert('请求失败: ' + e.message); this.textContent = '添加'; this.disabled = false; }
        };
    }

    // ==================== 魔搭 MCP 广场 ====================

    function renderHubCard(hub, remotes) {
        const hasToken = msStatus && msStatus.has_token;
        const tokenBadge = hasToken
            ? '<span class="badge badge-green">已配置 Token</span>'
            : '<span class="badge badge-yellow">未配置 Token</span>';

        const connectedList = remotes.length > 0 ? remotes.map(r => `
            <div class="flex-between" style="padding:6px 8px;border-bottom:1px solid var(--border);font-size:13px;">
                <span><span style="color:var(--green);">●</span>
                    <span style="margin-left:4px;">${escapeHtml(r.name)}</span>
                    <span class="mono" style="color:var(--text-dim);font-size:11px;margin-left:6px;">${r.tool_count || 0} 工具</span>
                </span>
                <button class="btn btn-sm btn-danger" data-ms-action="disconnect" data-ms-name="${r.ms_name}">断开</button>
            </div>
        `).join('') : '<div style="color:var(--text-dim);font-size:13px;padding:8px 0;">尚未连接任何魔搭 MCP 服务</div>';

        return `
            <div class="card" style="margin-bottom:12px;border-color:var(--accent);">
                <div class="flex-between mb-8">
                    <div>
                        <span style="font-weight:600;font-size:15px;color:var(--accent);">${escapeHtml(hub.name)}</span>
                        <span class="mono" style="color:var(--text-dim);margin-left:8px;font-size:12px;">${escapeHtml(hub.key)}</span>
                    </div>
                    <div>${tokenBadge}</div>
                </div>
                <div style="font-size:13px;color:var(--text-dim);margin-bottom:12px;">${escapeHtml(hub.description)}</div>
                <div class="flex-between" style="font-size:12px;color:var(--text-dim);margin-bottom:12px;">
                    <span>已连接：<span style="color:var(--green);font-weight:600;">${hub.connected_count || 0}</span> 个服务</span>
                    <span>可用工具：<span style="color:var(--accent);font-weight:600;">${hub.total_tools || 0}</span> 个</span>
                </div>
                <div style="display:flex;gap:6px;align-items:center;margin-bottom:12px;">
                    <input class="input input-sm" id="ms-token-input" type="password"
                        placeholder="魔搭 API Token（可选，用于认证）..." style="flex:1;"
                        value="${escapeHtml(msStatus && msStatus.has_token ? '********' : '')}">
                    <button class="btn btn-sm" id="ms-token-save">💾 保存 Token</button>
                </div>
                <div style="background:var(--bg);border-radius:var(--radius);padding:4px 8px;">
                    <div class="flex-between" style="padding:6px 0;font-size:12px;color:var(--text-dim);font-weight:600;">
                        <span>📦 已连接的 MCP 服务</span>
                    </div>
                    ${connectedList}
                </div>
            </div>
        `;
    }

    function bindHubCardEvents() {
        document.getElementById('ms-token-save')?.addEventListener('click', async function () {
            const input = document.getElementById('ms-token-input');
            const token = input.value.trim();
            if (!token || token === '********') return;
            this.textContent = '⏳'; this.disabled = true;
            try {
                const r = await api.modelscopeSetToken(token);
                if (r.ok) { msStatus = await loadMsStatus(); render(); }
                else { alert('保存失败: ' + (r.error || '')); this.textContent = '💾 保存 Token'; this.disabled = false; }
            } catch (e) { alert('请求失败: ' + e.message); this.textContent = '💾 保存 Token'; this.disabled = false; }
        });
    }

    // ==================== 搜索 ====================

    function bindSearchEvents() {
        const input = document.getElementById('ms-search-input');
        if (!input) return;

        document.getElementById('ms-search-btn')?.addEventListener('click', doSearch);

        // Enter 键搜索
        input.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') { e.preventDefault(); doSearch(); }
        });

        document.getElementById('ms-search-clear')?.addEventListener('click', () => {
            searchKeyword = '';
            activeCategory = '';
            doSearch();
        });

        // 分类标签
        document.querySelectorAll('[data-ms-cat]').forEach(btn => {
            btn.addEventListener('click', function () {
                activeCategory = this.dataset.msCat;
                searchKeyword = document.getElementById('ms-search-input')?.value || '';
                doSearch();
            });
        });

        // 翻页
        document.querySelectorAll('[data-page]').forEach(btn => {
            btn.addEventListener('click', async function () {
                if (this.disabled) return;
                const page = Math.max(1, parseInt(this.dataset.page) || 1);
                searchLoading = true;
                currentPage = page;
                render();
                const cat = activeCategory === '全部' || activeCategory === '热门' || activeCategory === '' ? '' : activeCategory;
                const r = await searchMs(searchKeyword, cat, page);
                if (r) searchResult = r;
                searchLoading = false;
                render();
            });
        });

        // 一键连接 MCP（直接调用 deploy API）
        document.querySelectorAll('[data-ms-deploy]').forEach(btn => {
            btn.addEventListener('click', async function () {
                const serverId = this.dataset.msDeploy;
                const name = this.dataset.msName;
                this.textContent = '⏳'; this.disabled = true;
                this.style.pointerEvents = 'none';
                try {
                    const r = await api.modelscopeDeploy(serverId);
                    if (r && r.ok) {
                        mcps = await loadList();
                        msStatus = await loadMsStatus();
                        render();
                        showToast(`✅ ${name} 已连接成功！`, 'var(--green)');
                    } else if (r && r.is_local) {
                        // 本地命令型 MCP — 显示运行指南
                        showLocalMcpGuide(r);
                        this.textContent = '⚡ 一键连接';
                        this.disabled = false;
                        this.style.pointerEvents = '';
                    } else if (r && r.need_env) {
                        // 需要环境变量 — 弹窗配置
                        showEnvConfigDialog(r);
                        this.textContent = '⚡ 一键连接';
                        this.disabled = false;
                        this.style.pointerEvents = '';
                    } else {
                        const msg = (r && r.error) || '部署失败';
                        showToast(`❌ ${msg}`, 'var(--red)');
                        this.textContent = '⚡ 一键连接';
                        this.disabled = false;
                        this.style.pointerEvents = '';
                    }
                } catch (e) {
                    showToast('❌ 请求失败: ' + e.message, 'var(--red)');
                    this.textContent = '⚡ 一键连接';
                    this.disabled = false;
                    this.style.pointerEvents = '';
                }
            });
        });
    }

    // ==================== 帮助按钮 ====================

    function bindHelpButton() {
        document.getElementById('ms-help-btn')?.addEventListener('click', showMsHelpDialog);
    }

    function showMsHelpDialog() {
        const html = `
            <h3 style="margin-bottom:16px;">🌐 魔搭 MCP 广场 — 使用说明</h3>
            <div style="font-size:13px;line-height:1.8;color:var(--text);">
                <p style="margin-bottom:12px;"><strong>魔搭 MCP 广场</strong> 是阿里云魔搭社区推出的 MCP 服务平台，
                提供 <strong>9,200+</strong> 个托管 MCP 服务，涵盖搜索、地图、浏览器、绘图等领域。</p>

                <div style="background:var(--bg);border-radius:var(--radius);padding:12px 16px;margin-bottom:16px;">
                    <div style="font-weight:600;margin-bottom:8px;">📋 接入流程</div>
                    <ol style="padding-left:20px;margin:0;">
                        <li style="margin-bottom:6px;">在魔搭 <a href="https://www.modelscope.cn/my/myaccesstoken" target="_blank" style="color:var(--accent);">获取 API Token</a>，粘贴到上方输入框保存</li>
                        <li style="margin-bottom:6px;">在搜索框中搜索需要的 MCP 服务（如 "fetch"、"地图"）</li>
                        <li style="margin-bottom:6px;">点击服务卡片上的 <strong>「⚡ 一键连接」</strong>，自动部署并建立连接</li>
                        <li style="margin-bottom:6px;">连接成功后，Agent 即可自动调用该 MCP 的所有工具</li>
                        <li style="margin-bottom:0;">也可在 MCP 广场获取 SSE URL 手动添加</li>
                    </ol>
                </div>

                <div style="background:var(--bg);border-radius:var(--radius);padding:12px 16px;margin-bottom:16px;">
                    <div style="font-weight:600;margin-bottom:8px;">🔑 API Token（可选）</div>
                    <p style="margin:0 0 6px 0;">部分 MCP 服务需要认证，配置 Token 后可搜索全部服务：</p>
                    <ol style="padding-left:20px;margin:0;">
                        <li>访问 <a href="https://www.modelscope.cn/my/myaccesstoken" target="_blank" style="color:var(--accent);">魔搭访问令牌</a></li>
                        <li>新建 SDK/API 令牌 → 勾选 <strong>MCP:read</strong> 权限</li>
                        <li>复制令牌 → 粘贴到上方输入框 → 保存</li>
                    </ol>
                </div>

                <div style="background:var(--bg);border-radius:var(--radius);padding:12px 16px;">
                    <div style="font-weight:600;margin-bottom:8px;">💡 提示</div>
                    <ul style="padding-left:20px;margin:0;color:var(--text-dim);">
                        <li>支持按名称、作者搜索 MCP 服务，按分类筛选</li>
                        <li>SSE URL 默认有效期 <strong>24 小时</strong>，长期使用需创建长期令牌</li>
                        <li>最多同时连接 10 个 MCP 服务</li>
                        <li>已验证的 MCP 服务带有 ✅ 标记</li>
                    </ul>
                </div>
            </div>`;
        showModal(html, false);
    }

    // ==================== 连接弹窗 ====================

    function showMsConnectDialog(prefillId, prefillName) {
        const html = `
            <h3 style="margin-bottom:16px;">🔗 ${prefillId ? '添加 ' + escapeHtml(prefillName || prefillId) : '连接魔搭 MCP'}</h3>
            <div style="font-size:13px;color:var(--text-dim);margin-bottom:12px;line-height:1.6;">
                从 <a href="https://www.modelscope.cn/mcp?hosted=1" target="_blank" style="color:var(--accent);">魔搭 MCP 广场</a> 获取 SSE URL：
                <br>1. 搜索找到该服务 → 进入详情页
                <br>2. 点击「连接」→ 复制 SSE URL
                <br>3. 粘贴到下方输入框
            </div>
            <div style="margin-bottom:12px;">
                <label style="display:block;font-size:13px;color:var(--text-dim);margin-bottom:4px;">连接标识 (name)</label>
                <input class="input" id="ms-conn-name" value="${escapeHtml(prefillId || '')}" placeholder="例如: my-fetch">
            </div>
            <div style="margin-bottom:12px;">
                <label style="display:block;font-size:13px;color:var(--text-dim);margin-bottom:4px;">显示名称 (label)</label>
                <input class="input" id="ms-conn-label" value="${escapeHtml(prefillName || '')}" placeholder="例如: Fetch 网页抓取">
            </div>
            <div style="margin-bottom:12px;">
                <label style="display:block;font-size:13px;color:var(--text-dim);margin-bottom:4px;">SSE URL</label>
                <input class="input" id="ms-conn-url" placeholder="https://mcp.api-inference.modelscope.net/xxx/sse">
            </div>`;
        showModal(html, true);
        const confirmBtn = document.getElementById('modal-confirm');
        confirmBtn.textContent = '连接';
        confirmBtn.onclick = async function () {
            const name = document.getElementById('ms-conn-name').value.trim();
            const label = document.getElementById('ms-conn-label').value.trim() || name;
            const sseUrl = document.getElementById('ms-conn-url').value.trim();
            if (!name || !sseUrl) { alert('标识和 SSE URL 不能为空'); return; }
            this.textContent = '⏳ 连接中...'; this.disabled = true;
            try {
                const r = await api.modelscopeConnect(name, label, sseUrl);
                if (r.ok) { closeModal(); mcps = await loadList(); msStatus = await loadMsStatus(); render(); }
                else { alert('连接失败: ' + (r.error || '')); this.textContent = '连接'; this.disabled = false; }
            } catch (e) { alert('请求失败: ' + e.message); this.textContent = '连接'; this.disabled = false; }
        };
    }

    // ==================== 兜底渲染（API 不可用时） ====================

    function renderFallbackHubCard() {
        const hasToken = msStatus && msStatus.has_token;
        return `
            <div class="card" style="margin-bottom:12px;border-color:var(--accent);">
                <div class="flex-between mb-8">
                    <div>
                        <span style="font-weight:600;font-size:15px;color:var(--accent);">魔搭 MCP 广场</span>
                        <span class="mono" style="color:var(--text-dim);margin-left:8px;font-size:12px;">modelscope</span>
                    </div>
                    <div>${hasToken ? '<span class="badge badge-green">已配置 Token</span>' : '<span class="badge badge-red">未配置 Token</span>'}</div>
                </div>
                <div style="font-size:13px;color:var(--text-dim);margin-bottom:12px;">连接魔搭社区 9,200+ 托管 MCP 服务（SSE 协议），自动发现并调用工具</div>
                <div style="display:flex;gap:6px;align-items:center;margin-bottom:12px;">
                    <input class="input input-sm" id="ms-token-input" type="password"
                        placeholder="魔搭 API Token（必填，用于搜索和连接 MCP 服务）..." style="flex:1;"
                        value="${escapeHtml(hasToken ? '********' : '')}">
                    <button class="btn btn-sm" id="ms-token-save">💾 保存 Token</button>
                </div>
                <div style="background:var(--bg);border-radius:var(--radius);padding:4px 8px;">
                    <div style="padding:6px 0;font-size:12px;color:var(--text-dim);">
                        配置 Token 后即可搜索并一键连接 9,200+ 个托管 MCP 服务
                    </div>
                </div>
            </div>
        `;
    }

    // ==================== 辅助函数 ====================

    function showToast(text, bgColor) {
        const toast = document.createElement('div');
        toast.style.cssText = `position:fixed;bottom:24px;right:24px;background:${bgColor};color:#fff;padding:12px 20px;border-radius:var(--radius);font-size:13px;z-index:999;box-shadow:0 4px 12px rgba(0,0,0,0.3);animation:fadeIn 0.3s;max-width:400px;word-break:break-all;`;
        toast.textContent = text;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 4000);
    }

    function showLocalMcpGuide(data) {
        const cmdHtml = data.command_hint
            ? `<div style="background:var(--bg);border-radius:4px;padding:10px 12px;font-family:monospace;font-size:13px;margin:8px 0;">${escapeHtml(data.command_hint)}</div>`
            : '';
        const configHtml = data.server_config && data.server_config.length > 0
            ? `<pre style="background:var(--bg);border-radius:4px;padding:10px 12px;font-size:12px;overflow-x:auto;margin:8px 0;">${escapeHtml(JSON.stringify(data.server_config, null, 2))}</pre>`
            : '';
        const msName = data.name || data.server_id?.split('/').pop() || 'mcp';
        const msLabel = data.label || data.name || data.server_id || 'MCP';
        const html = `
            <h3 style="margin-bottom:16px;">⚠️ 本地命令型 MCP</h3>
            <div style="font-size:13px;line-height:1.8;color:var(--text);">
                <p style="margin-bottom:12px;"><strong>${escapeHtml(msLabel)}</strong> 是<strong style="color:var(--yellow);">本地命令型</strong> MCP 服务，不支持云端托管部署。</p>
                <div style="background:var(--bg);border-radius:var(--radius);padding:12px 16px;margin-bottom:12px;">
                    <div style="font-weight:600;margin-bottom:8px;">🖥️ 运行命令</div>
                    ${cmdHtml || configHtml || '<p style="color:var(--text-dim);">请在魔搭 MCP 广场查看运行说明</p>'}
                    <div style="margin-top:8px;font-size:12px;color:var(--text-dim);">服务 ID: <span class="mono">${escapeHtml(data.server_id || '')}</span></div>
                </div>

                <div style="background:var(--bg);border-radius:var(--radius);padding:12px 16px;margin-bottom:16px;">
                    <div style="font-weight:600;margin-bottom:8px;">🔗 手动连接（如果你已有 SSE URL）</div>
                    <p style="font-size:12px;color:var(--text-dim);margin-bottom:8px;">
                        本地运行 MCP 服务后，如果它对外提供 SSE 端点，可在此直接连接：
                    </p>
                    <input class="input" id="local-sse-url" type="text"
                        placeholder="https://mcp.api-inference.modelscope.net/xxx/sse 或 http://127.0.0.1:8080/sse"
                        style="margin-bottom:8px;">
                    <div style="display:flex;gap:6px;justify-content:flex-end;">
                        <button class="btn" onclick="closeModal()">取消</button>
                        <button class="btn btn-primary" id="local-sse-connect">🔗 确认连接</button>
                    </div>
                </div>
            </div>`;
        showModal(html, false);

        // 绑定连接按钮
        const connectBtn = document.getElementById('local-sse-connect');
        if (connectBtn) {
            connectBtn.addEventListener('click', async function () {
                const sseUrl = document.getElementById('local-sse-url')?.value.trim();
                if (!sseUrl) { alert('请输入 SSE URL'); return; }
                this.textContent = '⏳ 连接中...'; this.disabled = true;
                try {
                    const r = await api.modelscopeConnect(msName, msLabel, sseUrl);
                    if (r && r.ok) {
                        closeModal();
                        mcps = await loadList();
                        msStatus = await loadMsStatus();
                        render();
                        showToast(`✅ ${msLabel} 已连接成功！`, 'var(--green)');
                    } else {
                        alert('连接失败: ' + ((r && r.error) || ''));
                        this.textContent = '🔗 确认连接';
                        this.disabled = false;
                    }
                } catch (e) {
                    alert('请求失败: ' + e.message);
                    this.textContent = '🔗 确认连接';
                    this.disabled = false;
                }
            });
        }
    }

    // ==================== 已连接的魔搭服务 ====================

    function renderMsRemoteCard(m) {
        return `
            <div class="card" style="margin-bottom:8px;margin-left:24px;border-left:3px solid var(--accent);">
                <div class="flex-between">
                    <div>
                        <span style="font-weight:600;font-size:14px;color:var(--accent);">${escapeHtml(m.name)}</span>
                        <span class="mono" style="color:var(--text-dim);margin-left:8px;font-size:11px;">${escapeHtml(m.ms_name || '')}</span>
                    </div>
                    <div>
                        <span class="badge badge-green">已连接</span>
                        <span class="badge badge-purple">${m.tool_count || 0} 个工具</span>
                    </div>
                </div>
                <div style="margin-top:8px;display:flex;gap:6px;">
                    <button class="btn btn-sm btn-danger" data-ms-action="disconnect" data-ms-name="${escapeHtml(m.ms_name || m.key?.replace('ms_', '') || '')}">🔌 断开</button>
                </div>
            </div>
        `;
    }

    function bindMsCardEvents() {
        document.querySelectorAll('[data-ms-action]').forEach(btn => {
            btn.addEventListener('click', async function () {
                const name = this.dataset.msName;
                this.textContent = '⏳'; this.disabled = true;
                try {
                    const r = await api.modelscopeDisconnect(name);
                    if (r.ok) { mcps = await loadList(); msStatus = await loadMsStatus(); render(); }
                    else { alert('断开失败: ' + (r.error || '')); this.textContent = '断开'; this.disabled = false; }
                } catch (e) { alert('请求失败: ' + e.message); this.textContent = '断开'; this.disabled = false; }
            });
        });
    }
}
