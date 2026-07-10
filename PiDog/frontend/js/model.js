/* ============================================================
   model.js — 模型选择页面：逻辑模型 + 图片生成 + 图片理解
   ============================================================ */

async function renderModelPage(container) {
    // 并行加载三类模型状态
    const [logicStatus, imgGenStatus, imgUndStatus] = await Promise.all([
        api.getModelStatus(),
        api.getImgGenStatus(),
        api.getImgUndStatus(),
    ]);

    function renderProviderCard(p, status, isCurrent, switchFn) {
        const keyLabel = p.has_key
            ? '<span class="badge badge-green">已配置 Key</span>'
            : '<span class="badge badge-red">未配置 Key</span>';

        const modelBtns = p.models.map(m => {
            const isActive = isCurrent && m === status.current_model;
            return `<button class="btn btn-sm model-select-btn ${isActive ? 'btn-primary' : ''}"
                data-provider="${p.key}" data-model="${m}">
                ${m} ${isActive ? '✅' : ''}
            </button>`;
        }).join('');

        return `
            <div class="provider-card ${isCurrent ? 'active' : ''}">
                <div class="provider-header">
                    <span class="provider-name">${p.name} ${isCurrent ? '<span class="badge badge-purple">当前</span>' : ''}</span>
                    <span>${keyLabel}</span>
                </div>
                <div class="provider-url">${p.base_url}</div>
                <div class="provider-models-label">可用模型：</div>
                <div class="provider-models">
                    ${modelBtns}
                </div>
                <div class="provider-key-row">
                    <input class="input input-sm" id="key-${p.key}" type="password"
                        placeholder="自定义 API Key（留空使用默认）...">
                    <button class="btn btn-sm" data-action="save-key" data-provider="${p.key}">保存 Key</button>
                </div>
            </div>
        `;
    }

    function bindEvents(containerEl, statusObj, refreshFn, switchApiFn) {
        // Model button click
        containerEl.querySelectorAll('.model-select-btn').forEach(btn => {
            btn.addEventListener('click', async function () {
                const provider = this.dataset.provider;
                const model = this.dataset.model;
                if (provider === statusObj.current_provider && model === statusObj.current_model) return;

                this.textContent = '⏳';
                try {
                    const r = await switchApiFn(provider, model);
                    if (r.ok) {
                        const newStatus = await refreshFn();
                        Object.assign(statusObj, newStatus);
                        render();
                    }
                } catch (e) {
                    alert('Switch failed: ' + e.message);
                    render();
                }
            });
        });

        // Save Key button
        containerEl.querySelectorAll('[data-action="save-key"]').forEach(btn => {
            btn.addEventListener('click', async function () {
                const provider = this.dataset.provider;
                const keyInput = document.getElementById(`key-${provider}`);
                const key = keyInput.value.trim();
                if (!key) return;

                this.textContent = '⏳';
                try {
                    const r = await switchApiFn(provider, null, key);
                    if (r.ok) {
                        const newStatus = await refreshFn();
                        Object.assign(statusObj, newStatus);
                        render();
                    }
                } catch (e) {
                    alert('Save failed: ' + e.message);
                    render();
                }
            });
        });
    }

    function render() {
        // ---- 逻辑模型卡片 ----
        const logicCards = logicStatus.providers.map(p =>
            renderProviderCard(p, logicStatus, p.key === logicStatus.current_provider,
                (prov, mdl) => api.switchModel(prov, mdl))
        ).join('');

        // ---- 图片生成模型卡片 ----
        const imgGenCards = imgGenStatus.providers.map(p =>
            renderProviderCard(p, imgGenStatus, p.key === imgGenStatus.current_provider,
                (prov, mdl) => api.switchImgGen(prov, mdl))
        ).join('');

        // ---- 图片理解模型卡片 ----
        const imgUndCards = imgUndStatus.providers.map(p =>
            renderProviderCard(p, imgUndStatus, p.key === imgUndStatus.current_provider,
                (prov, mdl) => api.switchImgUnd(prov, mdl))
        ).join('');

        container.innerHTML = `
            <h2 style="margin-bottom:16px;">🧠 模型管理</h2>

            <div class="card mb-16">
                <div class="card-title">
                    当前逻辑模型：
                    <span style="color:var(--accent);">${logicStatus.current_provider}</span>
                    /
                    <span class="mono" style="color:var(--green);">${logicStatus.current_model}</span>
                </div>
                <div style="font-size:12px;color:var(--text-dim);margin-top:4px;">
                    模型选择后自动生效，并同步写入 confing.json
                </div>
            </div>

            <!-- ============ 逻辑模型 ============ -->
            <h3 style="margin:24px 0 12px;color:var(--text);font-size:15px;font-weight:600;">
                🧩 逻辑模型 <span style="color:var(--text-dim);font-weight:400;font-size:13px;">（文本对话与工具调用）</span>
            </h3>
            <div class="provider-grid" id="logic-model-grid">
                ${logicCards}
            </div>

            <!-- ============ 图片生成模型 ============ -->
            <h3 style="margin:32px 0 12px;color:var(--text);font-size:15px;font-weight:600;">
                🎨 图片生成模型 <span style="color:var(--text-dim);font-weight:400;font-size:13px;">（文生图、图生图）</span>
            </h3>
            <div class="provider-grid" id="img-gen-model-grid">
                ${imgGenCards}
            </div>
            <div style="font-size:12px;color:var(--text-dim);margin-bottom:8px;">
                当前：<span style="color:var(--green);">${imgGenStatus.current_model}</span>
            </div>

            <!-- ============ 图片理解模型 ============ -->
            <h3 style="margin:32px 0 12px;color:var(--text);font-size:15px;font-weight:600;">
                👁️ 图片理解模型 <span style="color:var(--text-dim);font-weight:400;font-size:13px;">（多模态识别、OCR、图片分析）</span>
            </h3>
            <div class="provider-grid" id="img-und-model-grid">
                ${imgUndCards}
            </div>
            <div style="font-size:12px;color:var(--text-dim);margin-bottom:8px;">
                当前：<span style="color:var(--green);">${imgUndStatus.current_model}</span>
            </div>
        `;

        // ---- 绑定事件 ----
        // 逻辑模型
        const logicGrid = container.querySelector('#logic-model-grid');
        bindEvents(logicGrid, logicStatus,
            () => api.getModelStatus(),
            (prov, mdl, key) => api.switchModel(prov, mdl, key));

        // 图片生成
        const genGrid = container.querySelector('#img-gen-model-grid');
        bindEvents(genGrid, imgGenStatus,
            () => api.getImgGenStatus(),
            (prov, mdl, key) => api.switchImgGen(prov, mdl, key));

        // 图片理解
        const undGrid = container.querySelector('#img-und-model-grid');
        bindEvents(undGrid, imgUndStatus,
            () => api.getImgUndStatus(),
            (prov, mdl, key) => api.switchImgUnd(prov, mdl, key));
    }

    render();
}
