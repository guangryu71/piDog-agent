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
        <h2 style="margin-bottom:16px;">🔧 已注册工具 <span style="color:var(--text-dim);font-size:13px;">（共 ${tools.length} 个）</span></h2>
        <div class="card">
            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th>工具名称</th>
                            <th>功能描述</th>
                            <th>模块路径</th>
                            <th>执行函数</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>
        </div>
    `;
}
