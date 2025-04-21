// sidebar_features.js
// Render sub-features (chức năng con) lên #sub-feature-panel khi chọn nhóm sidebar

document.addEventListener('DOMContentLoaded', function () {
    const groupFeatures = {
        download: [
            { label: 'Download Reports', url: '/download', icon: 'fa-download' },
            { label: 'Schedule Download', url: '/schedule', icon: 'fa-calendar-alt' },
            { label: 'Download History', url: '/history', icon: 'fa-history' },
            { label: 'Advanced Settings', url: '/settings', icon: 'fa-cog' }
        ],
        email: [
            { label: 'Bulk Email', url: '/bulk-email', icon: 'fa-envelope-open-text' },
            { label: 'Send History', url: '/email-history', icon: 'fa-paper-plane' }
        ]
        // Có thể bổ sung thêm nhóm khác ở đây
    };

    function renderSubFeatures(group) {
        const panel = document.getElementById('sub-feature-panel');
        if (!panel) return;
        const features = groupFeatures[group] || [];
        if (features.length === 0) {
            panel.innerHTML = '';
            return;
        }
        panel.innerHTML = `
            <section class="suggestion-cards">
                ${features.map(f => `
                    <div class="card" data-url="${f.url}">
                        <i class="fas ${f.icon} card-icon"></i>
                        <div class="card-content">
                            <h3 class="card-title">${f.label}</h3>
                            <p class="card-description">${f.desc || ''}</p>
                        </div>
                        <button class="card-button">Open</button>
                    </div>
                `).join('')}
            </section>
        `;
        // Thêm sự kiện click cho card
        panel.querySelectorAll('.card').forEach(card => {
            card.addEventListener('click', function(e) {
                const url = card.getAttribute('data-url');
                if (url) window.location.href = url;
            });
        });
    }

    // Xử lý click vào nhóm sidebar
    document.querySelectorAll('.sidebar-group').forEach(el => {
        el.addEventListener('click', function (e) {
            e.preventDefault();
            const group = this.getAttribute('data-group');
            renderSubFeatures(group);
            // Đánh dấu active
            document.querySelectorAll('.sidebar-group').forEach(sg => sg.classList.remove('active'));
            this.classList.add('active');
        });
    });

    // Tự động render nhóm đầu tiên khi load trang
    const firstGroup = document.querySelector('.sidebar-group');
    if (firstGroup) {
        firstGroup.click();
    }
});
