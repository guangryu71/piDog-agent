/* ============================================================
   model.js — 模型选择页面：单一主模型
   Agent 统一使用一个主模型，顶部统一 API Key
   ============================================================ */

async function renderModelPage(container) {
    const status = await api.getModelStatus();

    function renderCapabilityTag(caps, key, icon, label) {
        if (!caps || caps[key] === undefined) return '';
        const supported = caps[key];
        return `<span style="display:inline-flex;align-items:center;gap:3px;padding:3px 8px;border-radius:12px;font-size:11px;font-weight:500;${supported ? 'background:rgba(63,185,80,0.15);color:var(--green);' : 'background:rgba(110,118,129,0.1);color:var(--text-dim);'}">${icon} ${label} ${supported ? '✅' : '❌'}</span>`;
    }

    function render() {
        const hasKey = status.has_global_key;
        const hasOcrKey = status.has_ocr_key;

        const cards = status.providers.map(p => {
            const isCurrent = p.key === status.current_provider;

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
                    </div>
                    <div class="provider-url">${p.base_url}</div>
                    <div class="provider-models-label">可用模型：</div>
                    <div class="provider-models">
                        ${modelBtns}
                    </div>
                </div>
            `;
        }).join('');

        container.innerHTML = `
            <h2 style="margin-bottom:16px;">🧠 Agent 主模型</h2>

            <!-- ====== 顶部统一 API Key ====== -->
            <div class="card mb-16">
                <div class="card-title">
                    🔑 API Key
                    <span style="font-weight:400;font-size:12px;color:var(--text-dim);margin-left:8px;">
                        所有提供商共用此 Key
                    </span>
                </div>
                <div style="display:flex;gap:8px;align-items:center;">
                    <input class="input" id="global-api-key" type="password"
                        style="flex:1;"
                        placeholder="${hasKey ? '已配置 API Key（输入新值覆盖）...' : '输入 API Key ...'}"
                        ${hasKey ? 'data-has-key="1"' : ''}>
                    <button class="btn btn-primary" id="save-global-key-btn">
                        ${hasKey ? '更新 Key' : '保存 Key'}
                    </button>
                </div>
                <div style="font-size:12px;color:var(--text-dim);margin-top:6px;">
                    ${hasKey
                        ? '<span style="color:var(--green);">✅ 已配置 API Key</span>'
                        : '<span style="color:var(--red);">⚠️ 未配置 API Key</span>'
                    }
                    · Key 保存后自动写入 confing.json，重启后保留
                </div>
            </div>

            <!-- ====== DeepSeek-OCR 专用 API Key ====== -->
            <div class="card mb-16">
                <div class="card-title">
                    📝 DeepSeek-OCR 专用 Key
                    <span style="font-weight:400;font-size:12px;color:var(--text-dim);margin-left:8px;">
                        用于图片文字提取（OCR）
                    </span>
                </div>
                <div style="display:flex;gap:8px;align-items:center;">
                    <input class="input" id="ocr-api-key" type="password"
                        style="flex:1;"
                        placeholder="${hasOcrKey ? '已配置 OCR Key（输入新值覆盖）...' : '输入 DeepSeek API Key ...'}"
                        ${hasOcrKey ? 'data-has-key="1"' : ''}>
                    <button class="btn btn-primary" id="save-ocr-key-btn">
                        ${hasOcrKey ? '更新 Key' : '保存 Key'}
                    </button>
                </div>
                <div style="font-size:12px;color:var(--text-dim);margin-top:6px;">
                    ${hasOcrKey
                        ? '<span style="color:var(--green);">✅ 已配置 OCR Key</span>'
                        : '<span style="color:var(--red);">⚠️ 未配置 OCR Key</span>'
                    }
                    · 使用硅基流动 deepseek-ai/DeepSeek-OCR 模型进行文字识别
                </div>
            </div>

            <!-- ====== 当前模型状态 ====== -->
            <div class="card mb-16">
                <div class="card-title">
                    当前模型：
                    <span style="color:var(--accent);">${status.current_provider}</span>
                    /
                    <span class="mono" style="color:var(--green);">${status.current_model}</span>
                </div>
                <div style="font-size:12px;color:var(--text-dim);margin-top:8px;">
                    Agent 统一使用此模型进行对话、工具调用等所有工作。
                    选择下方模型后自动生效，重启后保留。
                </div>
                <!-- 能力标签 -->
                <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:8px;">
                    ${renderCapabilityTag(status.capabilities, 'vision', '👁️', '图片识别')}
                    ${renderCapabilityTag(status.capabilities, 'image_gen', '🎨', '图片生成')}
                    ${renderCapabilityTag(status.capabilities, 'ocr', '📝', '文字识别(OCR)')}
                    ${renderCapabilityTag(status.capabilities, 'reasoning', '🧠', '深度推理')}
                </div>
            </div>

            <!-- ====== 提供商列表 ====== -->
            <div class="provider-grid" id="model-grid">
                ${cards}
            </div>
        `;

        bindEvents();
    }

    function bindEvents() {
        // 保存全局 Key
        const saveKeyBtn = container.querySelector('#save-global-key-btn');
        const keyInput = container.querySelector('#global-api-key');
        if (saveKeyBtn && keyInput) {
            saveKeyBtn.addEventListener('click', async function () {
                const key = keyInput.value.trim();
                if (!key) return;
                this.textContent = '⏳';
                try {
                    const r = await api.saveApiKey(key);
                    if (r && r.ok !== false) {
                        const newStatus = await api.getModelStatus();
                        Object.assign(status, newStatus);
                        render();
                    }
                } catch (e) {
                    alert('保存失败: ' + e.message);
                    render();
                }
            });
        }

        // 保存 OCR Key
        const saveOcrBtn = container.querySelector('#save-ocr-key-btn');
        const ocrKeyInput = container.querySelector('#ocr-api-key');
        if (saveOcrBtn && ocrKeyInput) {
            saveOcrBtn.addEventListener('click', async function () {
                const key = ocrKeyInput.value.trim();
                if (!key) return;
                this.textContent = '⏳';
                try {
                    const r = await api.saveOcrApiKey(key);
                    if (r && r.ok !== false) {
                        const newStatus = await api.getModelStatus();
                        Object.assign(status, newStatus);
                        render();
                    }
                } catch (e) {
                    alert('保存失败: ' + e.message);
                    render();
                }
            });
        }

        // 模型按钮
        const grid = container.querySelector('#model-grid');
        if (!grid) return;
        grid.querySelectorAll('.model-select-btn').forEach(btn => {
            btn.addEventListener('click', async function () {
                const provider = this.dataset.provider;
                const model = this.dataset.model;
                if (provider === status.current_provider && model === status.current_model) return;

                this.textContent = '⏳';
                try {
                    const r = await api.switchModel(provider, model);
                    if (r && r.ok !== false) {
                        const newStatus = await api.getModelStatus();
                        Object.assign(status, newStatus);
                        render();
                    }
                } catch (e) {
                    alert('切换失败: ' + e.message);
                    render();
                }
            });
        });
    }

    render();
}
