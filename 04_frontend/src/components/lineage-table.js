import { store } from '../state/store.js';
import { STATE_COLOR, STATE_KR, FEATURE_LABEL, SIGNAL_LABEL, OVERRIDE_LABEL } from '../utils/formatters.js';

function render(rows) {
  const tbody = document.getElementById('lineage-body');
  if (!tbody) return;
  tbody.innerHTML = '';

  if (!rows || rows.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="py-4 text-center text-slate-600">데이터 없음</td></tr>';
    return;
  }

  const seen   = new Set();
  const unique = rows.filter(r => {
    const key = `${r.feature_kind}|${r.signal_kind}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });

  unique.forEach(r => {
    const stateColor = STATE_COLOR[r.state_band] ?? '#94a3b8';
    const ovHtml     = r.override_applied !== 'none'
      ? ` <span class="text-amber-400 text-xs">[${OVERRIDE_LABEL[r.override_applied] ?? r.override_applied}]</span>`
      : '';
    const tr = document.createElement('tr');
    tr.className = 'text-xs text-slate-300';
    tr.innerHTML = `
      <td class="py-2 pr-4 font-medium">${FEATURE_LABEL[r.feature_kind] ?? r.feature_kind}</td>
      <td class="py-2 pr-4 font-mono text-sky-300">${r.feature_score.toFixed(4)}</td>
      <td class="py-2 pr-4">${SIGNAL_LABEL[r.signal_kind] ?? r.signal_kind}</td>
      <td class="py-2 pr-4 font-mono text-emerald-300">${r.signal_score.toFixed(4)}</td>
      <td class="py-2 pr-4 font-mono" style="color:${stateColor};">${r.s_priority.toFixed(4)}</td>
      <td class="py-2">
        <span class="state-badge state-${r.state_band}">${STATE_KR[r.state_band] ?? r.state_band}</span>
        ${ovHtml}
      </td>
    `;
    tbody.appendChild(tr);
  });
}

export function mount() {
  store.subscribe('lineage', render);
}
