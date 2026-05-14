import { store } from '../state/store.js';
import { loadDetail } from '../api/segments.js';
import { STATE_KR, OVERRIDE_LABEL, spColor } from '../utils/formatters.js';

function renderSkeleton(container, countEl) {
  if (countEl) countEl.textContent = '로딩 중…';
  container.innerHTML = Array.from({ length: 4 }, () => `
    <div class="skeleton-card">
      <div class="flex items-start justify-between gap-2 mb-2">
        <div class="flex-1">
          <div class="skeleton skeleton-line skeleton-title"></div>
          <div class="skeleton skeleton-line skeleton-sub mt-1"></div>
        </div>
        <div class="skeleton" style="width:64px;height:18px;border-radius:9999px;flex-shrink:0;"></div>
      </div>
      <div class="skeleton skeleton-bar w-full"></div>
    </div>
  `).join('');
}

function render(list) {
  const countEl    = document.getElementById('seg-count');
  const container  = document.getElementById('segment-list');
  if (!container) return;

  if (store.get('segmentsLoading')) {
    renderSkeleton(container, countEl);
    return;
  }

  if (countEl) countEl.textContent = `${list.length}개 구간`;
  container.innerHTML = '';

  if (list.length === 0) {
    container.innerHTML = '<div class="text-red-400 text-sm p-2">구간 목록 로드 실패</div>';
    return;
  }

  list.forEach(seg => {
    const card = document.createElement('div');
    card.className = 'seg-card rounded-lg p-3';
    card.id = `card-${seg.segment_id}`;
    const sp       = seg.s_priority;
    const spPct    = Math.round(sp * 100);
    const barColor = spColor(sp);
    const ovHtml   = seg.override_applied !== 'none'
      ? `<span class="text-xs text-amber-400">[${OVERRIDE_LABEL[seg.override_applied] ?? seg.override_applied}]</span>`
      : '';
    card.innerHTML = `
      <div class="flex items-start justify-between gap-2 mb-2">
        <div>
          <div class="font-semibold text-sm leading-tight">${seg.segment_name}</div>
          <div class="text-xs text-slate-500 mt-0.5">${seg.segment_id}</div>
        </div>
        <span class="state-badge state-${seg.state_band} flex-shrink-0 mt-0.5">
          ${STATE_KR[seg.state_band] ?? seg.state_band}
        </span>
      </div>
      <div class="flex items-center gap-2">
        <div class="sp-bar-bg flex-1">
          <div class="sp-bar-fill" style="width:${spPct}%; background:${barColor};"></div>
        </div>
        <span class="text-xs font-mono" style="color:${barColor};">${sp.toFixed(3)}</span>
        ${ovHtml}
      </div>
    `;
    card.addEventListener('click', () => loadDetail(seg.segment_id));
    container.appendChild(card);
  });
}

export function mount() {
  store.subscribe('segments', render);
  store.subscribe('segmentsLoading', loading => {
    const container = document.getElementById('segment-list');
    const countEl   = document.getElementById('seg-count');
    if (loading && container) renderSkeleton(container, countEl);
  });

  store.subscribe('selectedId', segId => {
    document.querySelectorAll('.seg-card').forEach(c => c.classList.remove('active'));
    if (segId) {
      const card = document.getElementById(`card-${segId}`);
      if (card) card.classList.add('active');
    }
  });
}
