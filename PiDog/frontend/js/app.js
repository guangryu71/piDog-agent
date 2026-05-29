/* ============================================================
   app.js — 主控制器：侧边栏导航 + 页面切换
   ============================================================ */

(function () {
    const main = document.getElementById('main-content');
    const navItems = document.querySelectorAll('.nav-item');

    // 页面渲染器映射
    const pages = {
        chat: renderChatPage,
        model: renderModelPage,
        tools: renderToolsPage,
        skills: renderSkillsPage,
        tokens: renderTokensPage,
    };

    // 当前页面
    let currentPage = 'chat';

    // ---- 导航切换 ----
    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const page = item.dataset.page;
            if (page === currentPage) return;

            navItems.forEach(n => n.classList.remove('active'));
            item.classList.add('active');
            currentPage = page;

            main.innerHTML = '';
            if (pages[page]) pages[page](main);
        });
    });

    // ---- 首次加载 ----
    pages.chat(main);

    // ---- Modal 工具 ----
    window.showModal = function (html, showButtons = true) {
        const overlay = document.getElementById('modal-overlay');
        const content = document.getElementById('modal-content');
        let buttonHtml = '';
        if (showButtons) {
            buttonHtml = `
                <div class="modal-actions">
                    <button class="btn" onclick="closeModal()">取消</button>
                    <button class="btn btn-primary" id="modal-confirm">确认</button>
                </div>`;
        }
        content.innerHTML = html + buttonHtml;
        overlay.classList.add('show');

        // 默认确认按钮关闭弹窗
        const confirmBtn = document.getElementById('modal-confirm');
        if (confirmBtn) {
            confirmBtn.onclick = closeModal;
        }
    };

    window.closeModal = function () {
        document.getElementById('modal-overlay').classList.remove('show');
    };

    document.getElementById('modal-overlay').addEventListener('click', function (e) {
        if (e.target === this) closeModal();
    });

    // 转义 HTML
    window.escapeHtml = function (str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    };

    // 格式化数字
    window.fmt = function (n) {
        if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
        if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
        return String(n);
    };

    // 格式化时间
    window.fmtTime = function (ts) {
        const d = new Date(ts);
        return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
    };
})();
