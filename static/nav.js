// ─── NAV YEAR SWITCHER ───
function initNav(currentYear, minYear, maxYear) {
  const stored = parseInt(localStorage.getItem('f1_year') || currentYear);
  const activeYear = (stored >= minYear && stored <= maxYear) ? stored : currentYear;

  // Build year dropdown
  const dropdown = document.getElementById('year-dropdown');
  if (dropdown) {
    for (let y = maxYear; y >= minYear; y--) {
      const opt = document.createElement('option');
      opt.value = y;
      opt.textContent = y;
      if (y === activeYear) opt.selected = true;
      dropdown.appendChild(opt);
    }
    dropdown.addEventListener('change', () => {
      localStorage.setItem('f1_year', dropdown.value);
      // Reload current page with new year context
      window.location.reload();
    });
  }

  // Active nav link
  const path = window.location.pathname;
  document.querySelectorAll('.nav-links a').forEach(a => {
    const href = a.getAttribute('href');
    if (href === '/' && path === '/') a.classList.add('active');
    else if (href !== '/' && path.startsWith(href)) a.classList.add('active');
  });

  return activeYear;
}

function getSelectedYear(fallback) {
  const stored = parseInt(localStorage.getItem('f1_year') || fallback);
  return stored;
}
