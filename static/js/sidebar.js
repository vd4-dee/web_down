// Handles sidebar toggle and panel switching

document.addEventListener('DOMContentLoaded', () => {
  // Sidebar toggle
  const sidebar = document.getElementById('sidebar');
  const toggle = document.getElementById('sidebar-toggle');
  const mainContent = document.querySelector('.main-content') || document.getElementById('main-content');
  const icon = toggle?.querySelector('i');
  if (toggle) {
    toggle.addEventListener('click', () => {
      document.body.classList.toggle('collapsed');
      sidebar.classList.toggle('collapsed');
      if(mainContent) mainContent.classList.toggle('collapsed');
      if(document.body.classList.contains('collapsed')) {
        icon.classList.remove('fa-angle-double-left');
        icon.classList.add('fa-angle-double-right');
      } else {
        icon.classList.remove('fa-angle-double-right');
        icon.classList.add('fa-angle-double-left');
      }
    });
  }

  // Sidebar navigation & panel switching
  const sidebarLinks = document.querySelectorAll('#sidebar .sidebar-link');
  const mainPanels = document.querySelectorAll('.main-panel');

  function switchPanel(targetId) {
    if (!targetId) return;
    mainPanels.forEach(panel => panel.style.display = 'none');
    const targetPanel = document.getElementById(targetId);
    if (targetPanel) {
      targetPanel.style.display = 'block';
      targetPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    sidebarLinks.forEach(link => link.classList.remove('active'));
    sidebarLinks.forEach(link => {
      if (link.getAttribute('data-target') === targetId) {
        link.classList.add('active');
      }
    });
  }

  sidebarLinks.forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const targetId = link.getAttribute('data-target');
      switchPanel(targetId);
    });
  });

  // On initial load, show first panel
  if (mainPanels.length > 0) {
    mainPanels.forEach(panel => panel.style.display = 'none');
    mainPanels[0].style.display = 'block';
    if(sidebarLinks.length > 0) sidebarLinks[0].classList.add('active');
  }
});
