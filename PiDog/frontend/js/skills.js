/* ============================================================
   skills.js — Skill CRUD 管理页面
   ============================================================ */

async function renderSkillsPage(container) {
    async function refresh() {
        const skills = await api.getSkills();

        const rows = skills.map(s => `
            <tr>
                <td><span class="mono" style="color:var(--accent);">${escapeHtml(s.key)}</span></td>
                <td style="max-width:300px;">${escapeHtml(s.description)}</td>
                <td>${escapeHtml(s.path)}</td>
                <td>
                    <label class="toggle" title="Enable/Disable">
                        <input type="checkbox" ${s.enabled ? 'checked' : ''} data-key="${s.key}" class="skill-toggle">
                        <span class="toggle-slider"></span>
                    </label>
                </td>
                <td>
                    <button class="btn btn-sm skill-edit" data-key="${s.key}" data-desc="${escapeHtml(s.description)}">✏️</button>
                    <button class="btn btn-sm btn-danger skill-delete" data-key="${s.key}">🗑</button>
                </td>
            </tr>
        `).join('');

        container.innerHTML = `
            <div class="flex-between mb-16">
                <h2>📦 Skills <span style="color:var(--text-dim);font-size:13px;">(${skills.length})</span></h2>
                <button class="btn btn-primary" id="skill-add-btn">+ Add Skill</button>
            </div>
            <div class="card">
                <div class="table-wrap">
                    <table>
                        <thead>
                            <tr><th>Key</th><th>Description</th><th>Path</th><th>Enabled</th><th>Actions</th></tr>
                        </thead>
                        <tbody>${rows}</tbody>
                    </table>
                </div>
            </div>
        `;

        // Toggle enable/disable
        container.querySelectorAll('.skill-toggle').forEach(toggle => {
            toggle.addEventListener('change', async function () {
                const key = this.dataset.key;
                await api.updateSkill(key, { enabled: this.checked });
            });
        });

        // Edit
        container.querySelectorAll('.skill-edit').forEach(btn => {
            btn.addEventListener('click', function () {
                const key = this.dataset.key;
                const desc = this.dataset.desc;
                showModal(`
                    <h3>Edit Skill: ${key}</h3>
                    <div class="mb-12">
                        <label style="font-size:12px;color:var(--text-dim);">Description</label>
                        <textarea class="textarea" id="edit-skill-desc" style="margin-top:4px;">${desc.replace(/"/g, '&quot;')}</textarea>
                    </div>
                `);
                document.getElementById('modal-confirm').addEventListener('click', async () => {
                    const newDesc = document.getElementById('edit-skill-desc').value.trim();
                    if (newDesc) {
                        await api.updateSkill(key, { description: newDesc });
                        closeModal();
                        refresh();
                    }
                });
            });
        });

        // Delete
        container.querySelectorAll('.skill-delete').forEach(btn => {
            btn.addEventListener('click', async function () {
                const key = this.dataset.key;
                if (!confirm(`Delete skill "${key}"? This will remove its code directory.`)) return;
                await api.deleteSkill(key);
                refresh();
            });
        });

        // Add
        document.getElementById('skill-add-btn').addEventListener('click', () => {
            showModal(`
                <h3>Add Skill</h3>
                <div class="mb-12">
                    <label style="font-size:12px;color:var(--text-dim);">Key</label>
                    <input class="input" id="add-skill-key" placeholder="e.g. my_skill" style="margin-top:4px;">
                </div>
                <div class="mb-12">
                    <label style="font-size:12px;color:var(--text-dim);">Description</label>
                    <textarea class="textarea" id="add-skill-desc" placeholder="What does this skill do?" style="margin-top:4px;"></textarea>
                </div>
            `);
            document.getElementById('modal-confirm').addEventListener('click', async () => {
                const key = document.getElementById('add-skill-key').value.trim();
                const desc = document.getElementById('add-skill-desc').value.trim();
                if (key && desc) {
                    const r = await api.addSkill(key, desc);
                    if (r.ok) { closeModal(); refresh(); }
                    else alert(r.error);
                }
            });
        });
    }

    refresh();
}
