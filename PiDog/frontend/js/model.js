/* ============================================================
   model.js — 模型选择页面
   ============================================================ */

async function renderModelPage(container) {
    let status = await api.getModelStatus();

    function render() {
        const cards = status.providers.map(p => `
            <div class="provider-card ${p.key === status.current_provider ? 'active' : ''}" data-provider="${p.key}">
                <div class="flex-between mb-8">
                    <div class="name">${p.name}</div>
                    ${p.key === status.current_provider ? '<span class="badge badge-green">active</span>' : ''}
                </div>
                <div class="url">${p.base_url}</div>
                <div class="mb-8" style="font-size:12px;color:var(--text-dim);margin-top:4px;">
                    Key: ${p.has_key ? '<span class="badge badge-green">configured</span>' : '<span class="badge badge-red">missing</span>'}
                    · Default: <span class="mono">${p.default_model}</span>
                </div>
                <div class="models">
                    ${p.models.map(m => `<span class="badge ${m === status.current_model && p.key === status.current_provider ? 'badge-purple' : ''}" style="cursor:pointer;" data-model="${m}" data-provider="${p.key}">${m}</span>`).join(' ')}
                </div>
            </div>
        `).join('');

        container.innerHTML = `
            <h2 style="margin-bottom:16px;">🧠 Model Management</h2>

            <div class="card mb-16">
                <div class="card-title">Current: <span style="color:var(--accent);">${status.current_provider}</span> / <span class="mono">${status.current_model}</span></div>
            </div>

            <div class="card mb-16">
                <div class="card-title">🔑 Custom API Key</div>
                <div style="display:flex;gap:8px;">
                    <input class="input" id="custom-key" type="password" placeholder="Enter API key to override all providers...">
                    <button class="btn btn-primary" id="save-key">Save Key</button>
                </div>
            </div>

            <div class="provider-grid">
                ${cards}
            </div>
        `;

        // Provider card click → switch provider
        container.querySelectorAll('.provider-card').forEach(card => {
            card.addEventListener('click', async function () {
                const provider = this.dataset.provider;
                if (provider === status.current_provider) return;
                const r = await api.switchModel(provider);
                if (r.ok) {
                    status = await api.getModelStatus();
                    render();
                }
            });
        });

        // Model badge click → switch model within provider
        container.querySelectorAll('.badge[data-model]').forEach(badge => {
            badge.addEventListener('click', async function (e) {
                e.stopPropagation();
                const provider = this.dataset.provider;
                const model = this.dataset.model;
                if (provider === status.current_provider && model === status.current_model) return;
                const r = await api.switchModel(provider, model);
                if (r.ok) {
                    status = await api.getModelStatus();
                    render();
                }
            });
        });

        // Custom key
        document.getElementById('save-key').addEventListener('click', async () => {
            const key = document.getElementById('custom-key').value.trim();
            if (!key) return;
            const r = await api.switchModel(status.current_provider, status.current_model, key);
            if (r.ok) {
                status = await api.getModelStatus();
                render();
            }
        });
    }

    render();
}
