import { store } from '../state/store.js';
import { STATE_KR } from '../utils/formatters.js';

const BRIEFING_BORDER = {
  ImmediatePreWatering: '#ef4444',
  PriorityPreWatering:  '#f97316',
  ReviewPreWatering:    '#eab308',
  EnhancedMonitoring:   '#3b82f6',
  GeneralManagement:    '#22c55e',
};

function renderBriefing(data) {
  if (!data) return;

  const btn    = document.getElementById('briefing-refresh');
  const report = document.getElementById('briefing-report');
  const top5   = document.getElementById('briefing-top5');

  if (btn) { btn.disabled = false; btn.textContent = '새로고침'; }

  if (data.error) {
    if (report) report.innerHTML = '<span class="text-red-400 italic">브리핑 로드 실패. 서버 상태를 확인하세요.</span>';
    return;
  }

  const providerEl = document.getElementById('briefing-provider');
  if (providerEl) {
    const provider = data.llm_provider ?? 'none';
    if (provider === 'gemini') {
      providerEl.textContent = 'Gemini 2.0 Flash';
      providerEl.className   = 'text-xs px-2 py-0.5 rounded-full bg-blue-900/50 text-blue-300';
    } else if (provider === 'anthropic') {
      providerEl.textContent = 'Claude';
      providerEl.className   = 'text-xs px-2 py-0.5 rounded-full bg-purple-900/50 text-purple-300';
    } else if (provider === 'lm_studio') {
      providerEl.textContent = 'LM Studio (로컬)';
      providerEl.className   = 'text-xs px-2 py-0.5 rounded-full bg-emerald-900/50 text-emerald-300';
    } else if (provider === 'structured') {
      providerEl.textContent = '구조화 텍스트';
      providerEl.className   = 'text-xs px-2 py-0.5 rounded-full bg-slate-700 text-slate-400';
    } else {
      providerEl.textContent = 'fallback';
      providerEl.className   = 'text-xs px-2 py-0.5 rounded-full bg-slate-700 text-slate-400';
    }
  }

  if (report) {
    const raw = data.report ?? '';
    if (typeof window.marked !== 'undefined') {
      report.innerHTML = window.marked.parse(raw);
    } else {
      report.textContent = raw;
    }
  }

  if (top5) {
    top5.innerHTML = '';
    (data.top_segments ?? []).forEach((seg, idx) => {
      const color   = BRIEFING_BORDER[seg.state_band] ?? '#475569';
      const stateKr = STATE_KR[seg.state_band] ?? seg.state_band;
      const sp      = (seg.s_priority ?? 0).toFixed(3);
      const card    = document.createElement('div');
      card.className  = 'flex-shrink-0 rounded-lg p-3 min-w-40 border-l-4';
      card.style.cssText = `background:#0f172a; border-left-color:${color};`;
      card.innerHTML = `
        <div class="text-xs text-slate-500 mb-0.5">${idx + 1}위</div>
        <div class="font-bold text-sm" style="color:${color};">${seg.sigun}</div>
        <div class="text-xs text-slate-400 mt-1">S_priority: <span class="font-mono text-sky-300">${sp}</span></div>
        <div class="text-xs mt-0.5" style="color:${color};">${stateKr}</div>
        <div class="text-xs text-slate-500 mt-1 leading-tight">${seg.action_summary ?? ''}</div>
      `;
      top5.appendChild(card);
    });
  }
}

export function mount() {
  store.subscribe('briefing', renderBriefing);

  store.subscribe('briefingLoading', loading => {
    const btn    = document.getElementById('briefing-refresh');
    const report = document.getElementById('briefing-report');
    const top5   = document.getElementById('briefing-top5');
    if (loading) {
      if (btn) { btn.disabled = true; btn.textContent = '생성 중…'; }
      if (report) report.innerHTML = `
        <div class="flex flex-col gap-2">
          <div class="skeleton skeleton-line" style="width:90%;height:11px;"></div>
          <div class="skeleton skeleton-line" style="width:80%;height:11px;"></div>
          <div class="skeleton skeleton-line" style="width:85%;height:11px;"></div>
          <div class="skeleton skeleton-line" style="width:60%;height:11px;"></div>
          <div class="skeleton skeleton-line mt-2" style="width:75%;height:11px;"></div>
          <div class="skeleton skeleton-line" style="width:88%;height:11px;"></div>
        </div>`;
      if (top5) top5.innerHTML = Array.from({ length: 3 }, () => `
        <div class="flex-shrink-0 skeleton-card min-w-40" style="border-left:4px solid #334155;">
          <div class="skeleton skeleton-line" style="width:30%;height:9px;"></div>
          <div class="skeleton skeleton-line skeleton-title mt-1" style="height:14px;"></div>
          <div class="skeleton skeleton-line skeleton-sub mt-2"></div>
          <div class="skeleton skeleton-line skeleton-sub mt-1"></div>
        </div>`).join('');
    }
  });
}
