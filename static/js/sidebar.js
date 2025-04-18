// Handles sidebar toggle
document.addEventListener('DOMContentLoaded', () => {
  // Toggle Advanced Settings card
  const advCard = document.getElementById('advanced-settings-card');
  const advPanel = document.getElementById('advanced-settings');
  if (advCard && advPanel) {
    advCard.addEventListener('click', function(e) {
      e.preventDefault();
      if (advPanel.style.display === 'none' || advPanel.style.display === '') {
        advPanel.style.display = 'block';
        advPanel.scrollIntoView({behavior:'smooth', block:'center'});
      } else {
        advPanel.style.display = 'none';
      }
    });
  }

  const sidebar = document.getElementById('sidebar');
  const toggle = document.getElementById('sidebar-toggle');
  const mainContent = document.getElementById('main-content');
  toggle.addEventListener('click', () => {
    document.body.classList.toggle('collapsed');
    sidebar.classList.toggle('collapsed');
    mainContent.classList.toggle('collapsed');
  });
});
