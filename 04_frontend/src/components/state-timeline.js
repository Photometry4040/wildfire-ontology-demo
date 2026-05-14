import { store } from '../state/store.js';
import { STATE_KR } from '../utils/formatters.js';

const STATE_ACTION = {
  ImmediatePreWatering: '즉시 출동·주수·완료기록·재점검 예약',
  PriorityPreWatering:  '예정 출동·주수·완료기록',
  ReviewPreWatering:    '관할청 통보·일일 재점검 예약',
  EnhancedMonitoring:   '일 2회 재점검 예약',
  GeneralManagement:    '조치 없음',
  NotActionable:        '안전 위험 통보·위험 해소 후 재점검',
};

const STATE_EMOJI = {
  ImmediatePreWatering: '🔴',
  PriorityPreWatering:  '🔥',
  ReviewPreWatering:    '⚠️',
  EnhancedMonitoring:   '🔵',
  GeneralManagement:    '🟢',
  NotActionable:        '⛔',
};

function renderStateAction(detail) {
  const el = document.getElementById('state-action-container');
  if (!el || !detail) return;
  const action = STATE_ACTION[detail.state_band] ?? detail.state_band;
  const emoji  = STATE_EMOJI[detail.state_band] ?? '';
  const kr     = STATE_KR[detail.state_band] ?? detail.state_band;
  el.innerHTML = `
    <div class="state-action-card mb-4">
      <div class="action-label">현재 State — 지금 무엇이 필요한가</div>
      <div class="action-text">${emoji} ${kr}: ${action}</div>
    </div>
  `;
}

function renderTimeline(history) {
  const el = document.getElementById('status-timeline-container');
  if (!el) return;

  if (!history || history.length === 0) {
    el.innerHTML = '';
    return;
  }

  el.innerHTML = `
    <div class="flex items-center justify-between mb-3">
      <span class="text-xs font-semibold text-slate-400 uppercase tracking-wider">
        Status — 추론 파이프라인 이력
      </span>
      <span class="text-xs text-slate-600 font-mono">hover → 단계 설명</span>
    </div>
  `;

  const row = document.createElement('div');
  row.className = 'status-timeline';

  history.forEach((step, i) => {
    const stepEl = document.createElement('div');
    stepEl.className = `status-step${step.completed ? ' completed' : ''}`;

    // 연결선 (마지막 제외)
    if (i < history.length - 1) {
      const line = document.createElement('div');
      line.className = `status-line${step.completed ? ' completed' : ''}`;
      stepEl.appendChild(line);
    }

    const dot = document.createElement('div');
    dot.className = `status-dot${step.completed ? ' completed' : ''}`;
    stepEl.appendChild(dot);

    stepEl.innerHTML += `
      <div class="status-label">${step.label}</div>
      <div class="status-timestamp">${step.timestamp}</div>
      <div class="status-check">${step.completed ? '✓' : '○'}</div>
      <div class="status-tooltip"><strong>${step.label}</strong><br>${step.description}</div>
    `;

    row.appendChild(stepEl);
  });

  el.appendChild(row);
}

export function mount() {
  store.subscribe('detail', (detail) => {
    renderStateAction(detail);
    renderTimeline(detail?.status_history ?? []);
  });
}
