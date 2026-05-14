export function mount() {
  const btn = document.getElementById('btn-layer-example');
  if (btn) {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.layer-example').forEach(el => el.classList.toggle('hidden'));
    });
  }
}
