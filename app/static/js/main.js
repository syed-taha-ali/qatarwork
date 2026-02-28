// ─── QatarWork Main JS ────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {

  // Auto-dismiss alerts after 5 seconds
  const alerts = document.querySelectorAll('.alert');
  alerts.forEach(alert => {
    setTimeout(() => {
      alert.style.opacity = '0';
      alert.style.transition = 'opacity 0.5s';
      setTimeout(() => alert.remove(), 500);
    }, 5000);
  });

  // Confirm before all dangerous form submits (double safety)
  document.querySelectorAll('form[data-confirm]').forEach(form => {
    form.addEventListener('submit', e => {
      const msg = form.dataset.confirm;
      if (!confirm(msg)) e.preventDefault();
    });
  });

  // Active nav link highlighting
  const currentPath = window.location.pathname;
  document.querySelectorAll('.navbar-links a').forEach(link => {
    if (link.getAttribute('href') === currentPath) {
      link.style.color = '#8B1A1A';
      link.style.fontWeight = '600';
    }
  });

  // ─── Click-based Dropdown Menu ────────────────────────────────────────────
  const navUser = document.querySelector('.nav-user');
  const navDropdown = document.querySelector('.nav-dropdown');
  
  if (navUser && navDropdown) {
    // Toggle dropdown on user area click (works for both avatar and image)
    navUser.addEventListener('click', (e) => {
      e.stopPropagation();
      navDropdown.classList.toggle('show');
    });

    // Close dropdown when clicking anywhere else
    document.addEventListener('click', (e) => {
      if (!navUser.contains(e.target)) {
        navDropdown.classList.remove('show');
      }
    });

    // Close dropdown when clicking a link inside it
    navDropdown.querySelectorAll('a').forEach(link => {
      link.addEventListener('click', () => {
        navDropdown.classList.remove('show');
      });
    });
  }

});
