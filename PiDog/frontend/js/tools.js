/* ============================================================
   tools.js — 工具展示页面
   ============================================================ */

async function renderToolsPage(container) {
    const tools = await api.getTools();

    const rows = tools.map(t => `
        <tr>
            <td><span class="mono" style="color:var(--accent);">${escapeHtml(t.name)}</span></td>
            <td>${escapeHtml(t.description)}</td>
            <td><span class="badge badge-yellow">${escapeHtml(t.module)}</span></td>
            <td><span class="mono">${escapeHtml(t.function_name)}</span></td>
        </tr>
    `).join('');

    container.innerHTML = `
        <h2 style="margin-bottom:16px;">🔧 Registered Tools <span style="color:var(--text-dim);font-size:13px;">(${tools.length})</span></h2>
        <div class="card">
            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>Description</th>
                            <th>Module</th>
                            <th>Function</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>
        </div>
    `;
}
