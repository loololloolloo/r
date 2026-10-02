document.addEventListener('click', (event) => {
  const trigger = event.target.closest('[data-rg-top]');
  if (!trigger) return;
  event.preventDefault();
  window.scrollTo({ top: 0, behavior: 'smooth' });
});
