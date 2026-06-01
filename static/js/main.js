// ── Flash message auto-hide ───────────────────────────
setTimeout(() => {
  document.querySelectorAll('.flash').forEach(el => {
    el.style.transition = 'opacity 0.5s';
    el.style.opacity = '0';
    setTimeout(() => el.remove(), 500);
  });
}, 3000);

// ── Active nav link highlight ─────────────────────────
const currentPath = window.location.pathname;
document.querySelectorAll('.nav-links a').forEach(link => {
  if (link.getAttribute('href') === currentPath) {
    link.style.color = '#ffffff';
    link.style.fontWeight = '700';
  }
});

// ── Listing card click anywhere ───────────────────────
document.querySelectorAll('.listing-card').forEach(card => {
  card.style.cursor = 'pointer';
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
  counter.style.cssText = 'color:#6b7280;float:right;font-size:0.75rem;';
  counter.textContent = `0 / ${max}`;
  ta.parentNode.appendChild(counter);
  ta.addEventListener('input', () => {
    counter.textContent = `${ta.value.length} / ${max}`;
    counter.style.color = ta.value.length > max * 0.9 ? '#ef4444' : '#6b7280';
  });
});
