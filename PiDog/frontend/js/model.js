/* ============================================================
   model.js — 模型选择页面
   ============================================================ */

async function renderModelPage(container) {
    let status = await api.getModelStatus();

    function render() {
        const cards = status.providers.map(p => {
            const isCurrent = p.key === status.current_provider;
            const isSameModel = p.key === status.current_provider;
            const keyLabel = p.has_key
                ? '<span class="badge badge-green">已配置 Key</span>'
                : '<span class="badge badge-red">未配置 Key</span>';

            const modelBtns = p.models.map(m => {
                const isActive = isSameModel && m === status.current_model;
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
        }).join('');

        container.innerHTML = `
            <h2 style="margin-bottom:16px;">🧠 模型管理</h2>

            <div class="card mb-16">
                <div class="card-title">
                    当前：
                    <span style="color:var(--accent);">${status.current_provider}</span>
                    /
                    <span class="mono" style="color:var(--green);">${status.current_model}</span>
                </div>
                <div style="font-size:12px;color:var(--text-dim);margin-top:4px;">
                    模型选择后自动生效，并同步写入 confing.json
                </div>
            </div>

            <div class="provider-grid">
                ${cards}
            </div>
        `;

        // ---- Model button click → switch to that model ----
        container.querySelectorAll('.model-select-btn').forEach(btn => {
            btn.addEventListener('click', async function () {
                const provider = this.dataset.provider;
                const model = this.dataset.model;
                if (provider === status.current_provider && model === status.current_model) return;

                this.textContent = '⏳';
                try {
                    const r = await api.switchModel(provider, model);
                    if (r.ok) {
                        status = await api.getModelStatus();
                        render();
                    }
                } catch (e) {
                    alert('Switch failed: ' + e.message);
                    render();
                }
            });
        });

        // ---- Save Key button ----
        container.querySelectorAll('[data-action="save-key"]').forEach(btn => {
            btn.addEventListener('click', async function () {
                const provider = this.dataset.provider;
                const keyInput = document.getElementById(`key-${provider}`);
                const key = keyInput.value.trim();
                if (!key) return;

                this.textContent = '⏳';
                try {
                    const r = await api.switchModel(provider, null, key);
                    if (r.ok) {
                        status = await api.getModelStatus();
                        render();
                    }
                } catch (e) {
                    alert('Save failed: ' + e.message);
                    render();
                }
            });
        });
    }

    render();
}
