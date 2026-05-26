/* ============================================================
   tokens.js — Token 消耗统计页面
   ============================================================ */

async function renderTokensPage(container) {
    async function refresh(days = 30) {
        const stats = await api.getTokenStats(days);

        const providerBars = Object.entries(stats.by_provider || {}).map(([k, v]) => {
            const pct = stats.total_all ? ((v / stats.total_all) * 100).toFixed(1) : 0;
            return `<div class="mb-8" style="display:flex;align-items:center;gap:8px;">
                <span style="width:100px;font-size:12px;">${k}</span>
                <div style="flex:1;height:8px;background:var(--bg);border-radius:4px;overflow:hidden;">
                    <div style="width:${pct}%;height:100%;background:var(--accent);border-radius:4px;transition:width 0.5s;"></div>
                </div>
                <span style="font-size:12px;color:var(--text-dim);width:80px;text-align:right;">${fmt(v)} (${pct}%)</span>
            </div>`;
        }).join('') || '<span style="color:var(--text-dim);">No data</span>';

        const modelBars = Object.entries(stats.by_model || {}).sort((a, b) => b[1] - a[1]).slice(0, 8).map(([k, v]) => {
            const max = Math.max(...Object.values(stats.by_model || {}), 1);
            const pct = ((v / max) * 100).toFixed(0);
            return `<div class="mb-8" style="display:flex;align-items:center;gap:8px;">
                <span style="width:180px;font-size:11px;font-family:monospace;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${k}">${k}</span>
                <div style="flex:1;height:6px;background:var(--bg);border-radius:3px;overflow:hidden;">
                    <div style="width:${pct}%;height:100%;background:var(--purple);border-radius:3px;"></div>
                </div>
                <span style="font-size:11px;color:var(--text-dim);width:60px;text-align:right;">${fmt(v)}</span>
            </div>`;
        }).join('') || '<span style="color:var(--text-dim);">No data</span>';

        const recentRows = (stats.recent || []).slice().reverse().map(r => `
            <tr>
                <td><span class="mono">${fmtTime(r.timestamp)}</span></td>
                <td><span class="badge badge-purple">${r.provider}</span></td>
                <td><span class="mono" style="font-size:11px;">${r.model}</span></td>
                <td style="text-align:right;">${fmt(r.prompt_tokens)}</td>
                <td style="text-align:right;">${fmt(r.completion_tokens)}</td>
                <td style="text-align:right;font-weight:600;">${fmt(r.total_tokens)}</td>
            </tr>
        `).join('') || '<tr><td colspan="6" style="color:var(--text-dim);text-align:center;">No calls yet</td></tr>';

        container.innerHTML = `
            <div class="flex-between mb-16">
                <h2>📊 Token Usage</h2>
                <select class="select" style="width:auto;" id="token-days">
                    <option value="1">Today</option>
                    <option value="7">7 days</option>
                    <option value="30" selected>30 days</option>
                    <option value="90">90 days</option>
                </select>
            </div>

            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value">${fmt(stats.total_all)}</div>
                    <div class="stat-label">Total Tokens</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">${stats.calls}</div>
                    <div class="stat-label">API Calls</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">${fmt(stats.total_prompt)}</div>
                    <div class="stat-label">Prompt Tokens</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">${fmt(stats.total_completion)}</div>
                    <div class="stat-label">Completion Tokens</div>
                </div>
            </div>

            <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
                <div class="card">
                    <div class="card-title">By Provider</div>
                    ${providerBars}
                </div>
                <div class="card">
                    <div class="card-title">By Model</div>
                    ${modelBars}
                </div>
            </div>

            <div class="card" style="margin-top:16px;">
                <div class="card-title">Recent Calls</div>
                <div class="table-wrap">
                    <table>
                        <thead>
                            <tr><th>Time</th><th>Provider</th><th>Model</th><th style="text-align:right;">Prompt</th><th style="text-align:right;">Completion</th><th style="text-align:right;">Total</th></tr>
                        </thead>
                        <tbody>${recentRows}</tbody>
                    </table>
                </div>
            </div>
        `;

        document.getElementById('token-days').addEventListener('change', function () {
            refresh(parseInt(this.value));
        });
    }

    refresh();
}
