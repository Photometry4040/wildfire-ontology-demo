import { store, DEFAULT_WEIGHTS } from '../state/store.js';
import { runWithThresholds } from '../api/inference.js';
import { safeFetch } from '../api/client.js';
import { STATE_KR } from '../utils/formatters.js';

const SIGNAL_LABEL = {
  S_official: 'S_official',
  S_exposure: 'S_exposure ★',
  S_spread:   'S_spread',
  S_action:   'S_action',
  S_time:     'S_time',
};

const SIGNAL_DESC = {
  S_official: '공식 위험지수 가중치',
  S_exposure: '보호 대상 노출도 가중치 (발표 핵심)',
  S_spread:   '산불 확산 속도 가중치',
  S_action:   '작업 가능성 가중치',
  S_time:     '시간 긴급성 가중치',
};

let isOpen = true;

function calcTotal(weights) {
  return Object.values(weights).reduce((s, v) => s + v, 0);
}

function buildSliders(weights) {
  const container = document.getElementById('threshold-sliders');
  if (!container) return;
  container.innerHTML = '';

  Object.keys(DEFAULT_WEIGHTS).forEach(key => {
    const row = document.createElement('div');
    row.className = 'weight-row';
    const val = weights[key] ?? DEFAULT_WEIGHTS[key];

    row.innerHTML = `
      <label class="weight-label" title="${SIGNAL_DESC[key]}">${SIGNAL_LABEL[key]}</label>
      <input type="range" class="weight-slider" data-key="${key}"
             min="0" max="0.5" step="0.01" value="${val}">
      <span class="weight-value" id="wv-${key}">${val.toFixed(2)}</span>
    `;
    container.appendChild(row);
  });

  // 슬라이더 이벤트 — 실시간 합계 갱신
  container.querySelectorAll('.weight-slider').forEach(slider => {
    slider.addEventListener('input', () => {
      const key = slider.dataset.key;
      const newVal = parseFloat(slider.value);
      const current = store.get('thresholdWeights');
      const updated = { ...current, [key]: newVal };
      store.set('thresholdWeights', updated);
      document.getElementById(`wv-${key}`).textContent = newVal.toFixed(2);
      updateTotal(updated);
    });
  });

  updateTotal(weights);
}

function updateTotal(weights) {
  const total = calcTotal(weights);
  const el = document.getElementById('threshold-total');
  if (!el) return;
  const ok = Math.abs(total - 1.0) <= 0.05;
  el.className = `weight-total ${ok ? 'ok' : 'err'}`;
  el.textContent = `합계: ${total.toFixed(2)} ${ok ? '✓' : '⚠ 1.0 권장'}`;

  const applyBtn = document.getElementById('threshold-apply');
  if (applyBtn) applyBtn.disabled = !ok;
}

function renderResult(results) {
  const el = document.getElementById('threshold-results');
  if (!el) return;

  if (!results || results.length === 0) {
    el.innerHTML = '<div class="text-slate-600 text-xs">결과 없음</div>';
    return;
  }

  el.innerHTML = `
    <div class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 mt-3">
      Before / After 비교
    </div>
  `;

  results.forEach(r => {
    const row = document.createElement('div');
    row.className = `threshold-result-row${r.state_changed ? ' changed' : ''}`;
    const arrow = r.delta > 0 ? '↑' : (r.delta < 0 ? '↓' : '=');
    const deltaClass = r.delta > 0 ? 'up' : (r.delta < 0 ? 'down' : 'same');
    const stateHtml = r.state_changed
      ? `<span class="state-changed-badge">${STATE_KR[r.before_state] ?? r.before_state} → ${STATE_KR[r.after_state] ?? r.after_state}</span>`
      : `<span class="text-slate-600 text-xs">${STATE_KR[r.after_state] ?? r.after_state}</span>`;

    row.innerHTML = `
      <div>
        <div class="text-slate-300 font-medium text-xs">${r.segment_name}</div>
        <div class="mt-0.5">${stateHtml}</div>
      </div>
      <div class="text-right">
        <div class="font-mono text-xs text-slate-400">${r.before_sp.toFixed(4)}</div>
        <div class="font-mono text-xs font-bold sp-delta ${deltaClass}">${arrow} ${r.after_sp.toFixed(4)}</div>
      </div>
    `;
    el.appendChild(row);
  });
}

// ══════════════════════════════════════════════════════════
// 몬테카를로 히트맵 — S_exposure × S_official 격자 시뮬레이션
// ══════════════════════════════════════════════════════════

const STEPS = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50];
const N = STEPS.length;

// State Band → 위험도 숫자
function toLevel(sp) {
  if (sp >= 0.80) return 4;
  if (sp >= 0.60) return 3;
  if (sp >= 0.40) return 2;
  if (sp >= 0.20) return 1;
  return 0;
}

// 위험도 숫자 → 색상
function levelColor(v) {
  if (v < 0)  return '#1e293b'; // 불가능 조합 (합계 > 1)
  if (v <= 0) return '#22c55e';
  if (v <= 1) return `hsl(${Math.round(120 - v * 30)}, 70%, 42%)`;
  if (v <= 2) return '#eab308';
  if (v <= 3) return '#f97316';
  return '#ef4444';
}

// 위험도 숫자 → 한국어 State 이름
function levelName(v) {
  const names = ['일반관리', '모니터링강화', '검토예비주수', '우선예비주수', '즉시예비주수'];
  return names[Math.round(v)] ?? '불가';
}

// 몬테카를로 계산 및 히트맵 렌더
async function runMonteCarlo() {
  const loading = document.getElementById('monte-loading');
  const panel   = document.getElementById('monte-panel');
  const canvas  = document.getElementById('monte-canvas');
  if (!canvas) return;

  if (loading) loading.classList.remove('hidden');

  // 1. 원시 신호값 로드
  let segList;
  try {
    segList = await safeFetch('/api/segments/raw-signals');
  } catch {
    if (loading) loading.classList.add('hidden');
    return;
  }
  if (!segList?.length) { if (loading) loading.classList.add('hidden'); return; }

  // 2. S_spread/Action/Time은 현재 슬라이더 값으로 고정 (재정규화 없음)
  // → S_official/Exposure 변화의 효과가 그대로 S_priority에 반영됨
  const curW = store.get('thresholdWeights') || DEFAULT_WEIGHTS;
  const fixedSpread = curW.S_spread || 0.20;
  const fixedAction = curW.S_action || 0.20;
  const fixedTime   = curW.S_time   || 0.15;

  // 3. 10×10 격자 계산
  // grid[yi=S_official index][xi=S_exposure index] = 최악 구간 위험도(0~4)
  const grid = STEPS.map(off => STEPS.map(exp => {
    // MAX level across segments (최악 구간 기준 — 위험 구역 하나라도 높으면 경보)
    let maxLevel = -1;
    for (const seg of segList) {
      const sp = Math.min(
        off          * seg.s_official
        + exp        * seg.s_exposure
        + fixedSpread * seg.s_spread
        + fixedAction * seg.s_action
        + fixedTime   * seg.s_time,
        1.0  // cap
      );
      const lv = toLevel(sp);
      if (lv > maxLevel) maxLevel = lv;
    }
    return maxLevel;
  }));

  // 4. Canvas 렌더
  const ctx   = canvas.getContext('2d');
  const cellW = canvas.width  / N;
  const cellH = canvas.height / N;

  ctx.clearRect(0, 0, canvas.width, canvas.height);

  grid.forEach((row, yi) => {  // yi = S_official index (낮은 값이 아래)
    row.forEach((val, xi) => { // xi = S_exposure index (왼쪽이 작은 값)
      ctx.fillStyle = levelColor(val);
      ctx.fillRect(xi * cellW, (N - 1 - yi) * cellH, cellW, cellH);
    });
  });

  // 격자선 (연하게)
  ctx.strokeStyle = 'rgba(0,0,0,0.15)';
  ctx.lineWidth = 0.5;
  for (let i = 1; i < N; i++) {
    ctx.beginPath(); ctx.moveTo(i * cellW, 0); ctx.lineTo(i * cellW, canvas.height); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(0, i * cellH); ctx.lineTo(canvas.width, i * cellH); ctx.stroke();
  }

  // 현재 가중치 위치에 흰 원 표시
  const curOffIdx = STEPS.findIndex(v => Math.abs(v - curW.S_official) < 0.03);
  const curExpIdx = STEPS.findIndex(v => Math.abs(v - curW.S_exposure) < 0.03);
  if (curOffIdx >= 0 && curExpIdx >= 0) {
    const cx = (curExpIdx + 0.5) * cellW;
    const cy = (N - 1 - curOffIdx + 0.5) * cellH;
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.arc(cx, cy, 7, 0, Math.PI * 2);
    ctx.stroke();
    ctx.strokeStyle = '#000';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(cx, cy, 7, 0, Math.PI * 2);
    ctx.stroke();
  }

  // 현재 값 표시
  const offEl = document.getElementById('monte-cur-off');
  const expEl = document.getElementById('monte-cur-exp');
  if (offEl) offEl.textContent = curW.S_official.toFixed(2);
  if (expEl) expEl.textContent = curW.S_exposure.toFixed(2);

  // 5. 호버 tooltip
  canvas.onmousemove = e => {
    const rect = canvas.getBoundingClientRect();
    const mx   = (e.clientX - rect.left) * (canvas.width / rect.width);
    const my   = (e.clientY - rect.top)  * (canvas.height / rect.height);
    const xi   = Math.min(Math.floor(mx / cellW), N - 1);
    const yi   = N - 1 - Math.min(Math.floor(my / cellH), N - 1);
    const val  = grid[yi]?.[xi] ?? -1;
    const tip  = document.getElementById('monte-tooltip');
    if (!tip) return;
    if (val < 0) { tip.classList.add('hidden'); return; }
    tip.textContent = `S_off=${STEPS[yi].toFixed(2)} / S_exp=${STEPS[xi].toFixed(2)} → ${levelName(val)} (${val.toFixed(2)})`;
    tip.style.left = `${Math.min(mx + 10, canvas.width - 160)}px`;
    tip.style.top  = `${my - 24}px`;
    tip.classList.remove('hidden');
  };
  canvas.onmouseleave = () => {
    const tip = document.getElementById('monte-tooltip');
    if (tip) tip.classList.add('hidden');
  };

  if (loading) loading.classList.add('hidden');
  if (panel) panel.classList.remove('hidden');
}

export function mount() {
  // 결과 구독
  store.subscribe('thresholdResult', renderResult);
  store.subscribe('thresholdRunning', running => {
    const btn = document.getElementById('threshold-apply');
    if (btn) { btn.disabled = running; btn.textContent = running ? '계산 중…' : '▶ Apply & 비교'; }
  });

  // 헤더 토글
  const header = document.getElementById('threshold-header');
  if (header) {
    header.addEventListener('click', () => {
      isOpen = !isOpen;
      const body = document.getElementById('threshold-body');
      const icon = document.getElementById('threshold-chevron');
      if (body) body.style.display = isOpen ? 'block' : 'none';
      if (icon) icon.textContent = isOpen ? '▴' : '▾';
    });
  }

  // 슬라이더 초기 렌더
  const weights = store.get('thresholdWeights');
  buildSliders(weights);

  // Apply 버튼
  document.getElementById('threshold-apply')
    ?.addEventListener('click', () => {
      runWithThresholds(store.get('thresholdWeights'));
    });

  // 기본값 복원
  document.getElementById('threshold-reset')
    ?.addEventListener('click', () => {
      store.set('thresholdWeights', { ...DEFAULT_WEIGHTS });
      buildSliders({ ...DEFAULT_WEIGHTS });
    });

  // 몬테카를로 히트맵 버튼
  document.getElementById('threshold-monte')
    ?.addEventListener('click', runMonteCarlo);
}
