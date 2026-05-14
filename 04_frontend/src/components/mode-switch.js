import { store } from '../state/store.js';

const TABS = ['segments', 'pipeline', 'architecture', 'briefing'];

function setTab(tab) {
  if (!TABS.includes(tab)) return;

  TABS.forEach(t => {
    const panel = document.getElementById(`tab-panel-${t}`);
    if (panel) panel.classList.toggle('hidden', t !== tab);
  });

  TABS.forEach(t => {
    document.getElementById(`tab-btn-${t}`)?.classList.toggle('active', t === tab);
  });

  store.set('activeTab', tab);
  localStorage.setItem('active_tab', tab);
}

export function mount() {
  TABS.forEach(t => {
    document.getElementById(`tab-btn-${t}`)
      ?.addEventListener('click', () => setTab(t));
  });

  document.querySelectorAll('[data-tab]').forEach(btn => {
    btn.addEventListener('click', () => setTab(btn.dataset.tab));
  });

  // ⌘/Ctrl + 1~4 단축키
  document.addEventListener('keydown', e => {
    const isModifier = e.metaKey || e.ctrlKey;
    if (!isModifier) return;
    const idx = parseInt(e.key, 10) - 1;
    if (idx >= 0 && idx < TABS.length) {
      e.preventDefault();
      setTab(TABS[idx]);
    }
  });

  setTab(store.get('activeTab') || 'segments');
}

export { setTab };
