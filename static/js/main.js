// ── Toast Notifications ───────────────────────────────
function showToast(message, type = 'success') {
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const icons = {
    success: '✅',
    danger: '❌',
    warning: '⚠️',
    info: 'ℹ️'
  };

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <span class="toast-icon">${icons[type] || '✅'}</span>
    <span class="toast-msg">${message}</span>
    <button class="toast-close" onclick="this.parentElement.remove()">✕</button>
  `;

  container.appendChild(toast);

  // Animate in
  setTimeout(() => toast.classList.add('show'), 10);

  // Auto remove after 4 seconds
  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 400);
  }, 4000);
}

// Show flash messages as toasts
if (window._flashMessages) {
  window._flashMessages.forEach(([type, message]) => {
    setTimeout(() => showToast(message, type), 100);
  });
}

// ── Active nav link highlight ─────────────────────────
const currentPath = window.location.pathname;
document.querySelectorAll('.nav-links a').forEach(link => {
  if (link.getAttribute('href') === currentPath) {
    link.style.color = '#ffffff';
    link.style.fontWeight = '700';
  }
});

// ── Filter form auto submit on select change ──────────
document.querySelectorAll('.filter-bar select').forEach(select => {
  select.addEventListener('change', () => {
    select.closest('form').submit();
  });
});

// ── Confirm before exchange request ───────────────────
const exchangeForm = document.querySelector('.exchange-form');
if (exchangeForm) {
  exchangeForm.addEventListener('submit', (e) => {
    const confirmed = confirm('Send exchange request? Credits will be reserved on completion.');
    if (!confirmed) e.preventDefault();
  });
}

// ── Character counter for textarea ───────────────────
document.querySelectorAll('textarea').forEach(ta => {
  const max = 500;
  const counter = document.createElement('small');
  counter.style.cssText = 'color:#64748b;float:right;font-size:0.75rem;';
  counter.textContent = `0 / ${max}`;
  ta.parentNode.appendChild(counter);
  ta.addEventListener('input', () => {
    counter.textContent = `${ta.value.length} / ${max}`;
    counter.style.color = ta.value.length > max * 0.9 ? '#ef4444' : '#64748b';
  });
});