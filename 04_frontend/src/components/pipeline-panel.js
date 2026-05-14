import { sleep, showToast } from '../utils/toast.js';
import { store } from '../state/store.js';
import { loadSegments } from '../api/segments.js';
import { loadBriefing } from '../api/briefing.js';

function setNodeState(nodeName, state) {
  const node = document.querySelector(`[data-node="${nodeName}"]`);
  if (!node) return;
  node.classList.remove('active', 'done');
  if (state) node.classList.add(state);
}

function setPipelineMessage(msg) {
  const el = document.getElementById('pipeline-message');
  if (el) el.textContent = msg;
}

function setPipelineStatus(status) {
  const el = document.getElementById('pipeline-status');
  if (!el) return;
  el.textContent = status;
  el.className = `text-xs font-mono ${
    status === 'RUNNING' ? 'text-amber-400' :
    status === 'DONE'    ? 'text-emerald-400' : 'text-slate-400'
  }`;
  store.set('pipelineStatus', status);
}

async function runPipelineSequence() {
  const steps = [
    { node: 'trigger', message: '① TRIGGER · 박O수 예측 DB에서 위험지수 수신 → 임계치 비교', toast: '🚨 SEG-JN-C 위험지수 0.91 → 임계치 0.85 초과',      delay: 1200 },
    { node: 'state',   message: '② STATE · 5 Signal 가중평균 계산 → S_priority 산출',         toast: '⚙️ S_priority 0.706 (S_spread 0.87 최대 기여)',       delay: 1200 },
    { node: 'action',  message: '③ ACTION · 9 Override + 5 Decision Gate 적용',               toast: '🎯 Override GradeSevere 발동 → PriorityPreWatering', delay: 1200 },
    { node: 'lineage', message: '④ LINEAGE · 결정 근거 역추적 가능하게 저장',                 toast: '🔍 Feature 3종 → Signal 5종 → State 결정 체인 저장', delay: 1200 },
  ];

  setPipelineStatus('RUNNING');
  setNodeState('input', 'done');
  const arrows = document.querySelectorAll('.pipeline-arrow');
  arrows.forEach(a => a.classList.remove('flowing'));

  for (let i = 0; i < steps.length; i++) {
    const step = steps[i];
    if (arrows[i]) arrows[i].classList.add('flowing');
    setNodeState(step.node, 'active');
    setPipelineMessage(step.message);
    showToast(step.toast, 'info');
    await sleep(step.delay);
    if (arrows[i]) arrows[i].classList.remove('flowing');
    setNodeState(step.node, 'done');
  }

  await loadSegments();

  if (arrows[4]) arrows[4].classList.add('flowing');
  setNodeState('llm', 'active');
  setPipelineMessage('⑤ LLM · Gemini 한국어 브리핑 생성 중…');
  showToast('💬 유O수 영역: Gemini 자연어 변환 시작', 'info');
  await loadBriefing(true);
  if (arrows[4]) arrows[4].classList.remove('flowing');
  setNodeState('llm', 'done');

  setPipelineStatus('DONE');
  setPipelineMessage('✅ 파이프라인 완료. 곡성군 1위 — PriorityPreWatering');
  showToast('✅ 전체 파이프라인 완료', 'done');

  const btn = document.getElementById('btn-inference');
  if (btn) { btn.disabled = false; btn.textContent = '추론 재실행'; }
  store.set('inferenceRunning', false);
}

// ══════════════════════════════════════════════════════════
// 파이프라인 라이브 뷰 (4-Phase 상세 시각화)
// baseline API(/api/baseline/*) 사용 — onto-fire DB
// ══════════════════════════════════════════════════════════

const LV_BASE = 'http://localhost:8001/api/baseline';
let lvStep = 0;      // 0=idle, 1~4=phase
let lvRunning = false;

function lvWait(ms) { return new Promise(r => setTimeout(r, ms)); }

function lvSetPhase(id, state) {
  const el = document.getElementById(`lv-phase-${id}`);
  if (!el) return;
  el.className = `lv-phase ${state}`;
  const s = el.querySelector('.lv-phase-status');
  if (s) s.textContent = state.toUpperCase();
}

function lvLitArrow(n) {
  const el = document.getElementById(`lv-arrow-${n}`);
  if (el) el.classList.add('lit');
}

function lvShow(id) {
  const el = document.getElementById(`lv-section-${id}`);
  if (el) el.classList.remove('hidden');
}

function lvSetLock(locked) {
  lvRunning = locked;
  ['lv-btn-run', 'lv-btn-step', 'lv-btn-reset'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.disabled = locked;
  });
}

// ── Phase 1: TRIGGER ──────────────────────────────────────
async function lvRunTrigger() {
  lvSetPhase('trigger', 'running');
  const stepLabel = document.getElementById('lv-step-label');
  if (stepLabel) stepLabel.textContent = 'Phase 0: DB 초기화 중…';

  await fetch(`${LV_BASE}/init`, { method: 'POST' });

  if (stepLabel) stepLabel.textContent = 'Phase 1: 고위험 구역 감지 중…';
  const res = await fetch(`${LV_BASE}/trigger`);
  if (!res.ok) throw new Error('Trigger API 실패');
  const data = await res.json();

  lvRenderZoneCards(data.high_risk_zones, data.weather);
  lvShow('trigger');
  lvSetPhase('trigger', 'done');
  lvLitArrow(1);
  if (stepLabel) stepLabel.textContent = '⏭ 단계 2: 추론 INSERT';
  lvStep = 1;
}

function lvRenderZoneCards(zones, weather) {
  const container = document.getElementById('lv-zone-cards');
  if (!container) return;
  container.innerHTML = '';

  const wxMap = {};
  weather.forEach(w => { wxMap[w.zone] = w; });
  const allZones = [...new Set([...zones.map(z => z.zone), ...weather.map(w => w.zone)])];

  allZones.forEach(zoneName => {
    const risk = zones.find(z => z.zone === zoneName);
    const wx   = wxMap[zoneName] || {};
    const isCritical = risk?.critical;
    const isWarning  = risk && !isCritical;
    const cls = isCritical ? 'critical' : isWarning ? 'warning' : 'normal';
    const ri  = risk?.risk_index ?? 0;
    const gaugeColor = isCritical ? '#ef4444' : isWarning ? '#eab308' : '#22c55e';

    const card = document.createElement('div');
    card.className = `lv-zone-card ${cls}`;
    card.innerHTML = `
      <div class="flex items-center justify-between mb-2">
        <div class="text-sm font-bold text-slate-200">${zoneName}</div>
        ${isCritical ? '<span class="text-xs px-1.5 py-0.5 rounded-full bg-red-900/50 text-red-400">🚨 임계 초과</span>'
          : isWarning ? '<span class="text-xs px-1.5 py-0.5 rounded-full bg-yellow-900/40 text-yellow-400">⚠️ 경계</span>'
          : '<span class="text-xs px-1.5 py-0.5 rounded-full bg-green-900/30 text-green-400">✅ 정상</span>'}
      </div>
      ${risk ? `
        <div class="text-xs text-slate-400 mb-1">RI <span class="font-mono text-slate-200 font-bold">${ri.toFixed(2)}</span> · ${risk.risk_level}</div>
        <div class="lv-gauge-bar"><div class="lv-gauge-fill" style="width:${ri*100}%;background:${gaugeColor};"></div></div>
      ` : ''}
      ${wx.humidity != null ? `
        <div class="mt-2 flex gap-2 text-xs">
          <span class="${wx.dry ? 'text-red-400' : 'text-slate-400'}">💧 ${wx.humidity}% ${wx.dry ? '건조' : ''}</span>
          <span class="${wx.strong_wind ? 'text-orange-400' : 'text-slate-400'}">💨 ${wx.wind_speed}m/s ${wx.strong_wind ? '강풍' : ''}</span>
        </div>
      ` : ''}
    `;
    container.appendChild(card);
  });
}

// ── Phase 2: STATE (추론 INSERT) ──────────────────────────
async function lvRunInference() {
  lvSetPhase('state', 'running');
  lvShow('state');

  const ids = ['i01','i02','i03','i04'];
  ids.forEach(id => {
    const el = document.getElementById(`lv-infer-${id}`);
    if (el) el.querySelector('.lv-infer-check').textContent = '⟳';
  });

  const res = await fetch(`${LV_BASE}/infer`, { method: 'POST' });
  if (!res.ok) throw new Error('Infer API 실패');

  for (const id of ids) {
    const el = document.getElementById(`lv-infer-${id}`);
    if (el) {
      el.classList.add('done');
      el.querySelector('.lv-infer-check').textContent = '✓';
    }
    await lvWait(280);
  }

  lvSetPhase('state', 'done');
  lvLitArrow(2);
  const stepLabel = document.getElementById('lv-step-label');
  if (stepLabel) stepLabel.textContent = '⏭ 단계 3: 결정 결과';
  lvStep = 2;
}

// ── Phase 3: ACTION ───────────────────────────────────────
async function lvRunActions() {
  lvSetPhase('action', 'running');
  lvShow('action');

  const res = await fetch(`${LV_BASE}/actions`);
  if (!res.ok) throw new Error('Actions API 실패');
  const data = await res.json();

  const q = id => document.getElementById(id);

  if (q('lv-action-access'))
    q('lv-action-access').innerHTML = data.access_control.length
      ? data.access_control.map(a => `<div class="mb-1"><span class="text-red-400">■</span> ${a.zone}</div>`).join('')
      : '<span class="text-slate-600">해당 없음</span>';

  if (q('lv-action-evac'))
    q('lv-action-evac').innerHTML = data.evacuation.length
      ? data.evacuation.map(e => `<div class="mb-1">${e.incident} → <span class="text-amber-300">${e.settlement}</span></div>`).join('')
      : '<span class="text-slate-600">해당 없음</span>';

  if (q('lv-action-dispatch'))
    q('lv-action-dispatch').innerHTML = data.dispatch.length
      ? data.dispatch.map(d => `<div class="mb-1">${d.crew} + ${d.engine} + ${d.aircraft}</div>`).join('')
      : '<span class="text-slate-600">해당 없음</span>';

  if (q('lv-action-policy'))
    q('lv-action-policy').innerHTML = data.policy.length
      ? data.policy.map(p => `<div class="mb-1">보고 ${p.report_at} → 정책권고</div>`).join('')
      : '<span class="text-slate-600">해당 없음</span>';

  await lvWait(100);
  ['lv-card-access','lv-card-evac','lv-card-dispatch','lv-card-policy'].forEach((id, i) => {
    setTimeout(() => document.getElementById(id)?.classList.add('show'), i * 140);
  });

  lvSetPhase('action', 'done');
  lvLitArrow(3);
  const stepLabel = document.getElementById('lv-step-label');
  if (stepLabel) stepLabel.textContent = '⏭ 단계 4: Lineage 역추적';
  lvStep = 3;
}

// ── Phase 4: LINEAGE ──────────────────────────────────────
async function lvRunLineage() {
  lvSetPhase('lineage', 'running');
  lvShow('lineage');

  const res = await fetch(`${LV_BASE}/lineage`);
  if (!res.ok) throw new Error('Lineage API 실패');
  const data = await res.json();

  lvRenderLineageChains(data.lineage);
  lvSetPhase('lineage', 'done');
  const stepLabel = document.getElementById('lv-step-label');
  if (stepLabel) stepLabel.textContent = '✅ 완료';
  lvStep = 4;

  await lvWait(400);
  lvShow('complete');
}

function lvRenderLineageChains(lineage) {
  const container = document.getElementById('lv-lineage-chains');
  if (!container) return;
  container.innerHTML = '';

  lineage.forEach((item, idx) => {
    const { dry, strong_wind, low_fuel_moisture } = item.triggers;
    const isHigh = item.risk_index >= 0.85;

    const chain = document.createElement('div');
    chain.className = 'rounded-lg border border-slate-800 p-3';
    chain.style.background = '#020617';
    chain.innerHTML = `
      <div class="text-xs text-slate-500 mb-2 font-semibold">${item.zone} — <span class="${isHigh ? 'text-amber-400' : 'text-slate-400'}">${item.decision}</span></div>
      <div class="flex items-center gap-2 flex-wrap">
        <div class="lv-lineage-node ${isHigh ? 'lit' : ''}">
          <div class="text-xs text-slate-500">위험지수</div>
          <div class="font-mono font-bold text-sm ${isHigh ? 'text-red-400' : 'text-slate-300'}">${item.risk_index.toFixed(2)}</div>
          <div class="text-xs ${isHigh ? 'text-red-400' : 'text-slate-500'}">${item.risk_level}</div>
        </div>
        <div class="lv-ln-arrow ${isHigh ? 'lit' : ''}">→</div>
        <div class="lv-lineage-node ${(dry || strong_wind) ? 'lit' : ''}">
          <div class="text-xs text-slate-500">기상</div>
          <div class="text-xs ${dry ? 'text-orange-400' : 'text-slate-400'}">💧${item.humidity}% ${dry ? '⚠️' : ''}</div>
          <div class="text-xs ${strong_wind ? 'text-orange-400' : 'text-slate-400'}">💨${item.wind_speed}m/s ${strong_wind ? '⚠️' : ''}</div>
        </div>
        <div class="lv-ln-arrow ${(dry||strong_wind) ? 'lit' : ''}">→</div>
        <div class="lv-lineage-node ${low_fuel_moisture ? 'lit' : ''}">
          <div class="text-xs text-slate-500">연료수분</div>
          <div class="font-mono font-bold text-sm ${low_fuel_moisture ? 'text-red-400' : 'text-slate-300'}">${item.fuel_moisture}%</div>
          <div class="text-xs ${low_fuel_moisture ? 'text-red-400' : 'text-slate-500'}">${low_fuel_moisture ? '🔥' : '정상'}</div>
        </div>
        <div class="lv-ln-arrow ${isHigh ? 'lit' : ''}">→</div>
        <div class="lv-lineage-node ${isHigh ? 'lit' : ''}" style="${isHigh ? 'border-color:#f59e0b;' : ''}">
          <div class="text-xs text-slate-500">결정</div>
          <div class="text-xs font-bold ${isHigh ? 'text-amber-300' : 'text-slate-400'}">${item.decision}</div>
          <div class="text-xs ${isHigh ? 'text-amber-500' : 'text-slate-600'}">${isHigh ? '★추론' : '모니터링'}</div>
        </div>
      </div>
    `;

    setTimeout(() => {
      chain.querySelectorAll('.lv-lineage-node').forEach((n, i) => {
        setTimeout(() => n.classList.add('lit'), i * 180);
      });
    }, idx * 250);

    container.appendChild(chain);
  });
}

// ── 전체 / 단계별 / 초기화 ────────────────────────────────
async function runLiveView() {
  if (lvRunning) return;
  lvSetLock(true);
  resetLiveView();
  try {
    await lvRunTrigger();  await lvWait(700);
    await lvRunInference(); await lvWait(700);
    await lvRunActions();   await lvWait(700);
    await lvRunLineage();
  } catch(e) {
    showToast(`라이브 뷰 오류: ${e.message}`, 'warn');
    console.error(e);
  } finally {
    lvSetLock(false);
  }
}

async function stepLiveView() {
  if (lvRunning) return;
  lvSetLock(true);
  try {
    if (lvStep === 0)      { await lvRunTrigger(); }
    else if (lvStep === 1) { await lvRunInference(); }
    else if (lvStep === 2) { await lvRunActions(); }
    else if (lvStep === 3) { await lvRunLineage(); }
    else { showToast('모든 단계 완료. 초기화 후 재실행하세요.', 'info'); }
  } catch(e) {
    showToast(`오류: ${e.message}`, 'warn');
  } finally {
    lvSetLock(false);
  }
}

function resetLiveView() {
  ['trigger','state','action','lineage'].forEach(p => lvSetPhase(p, 'idle'));
  [1,2,3].forEach(n => {
    const el = document.getElementById(`lv-arrow-${n}`);
    if (el) el.classList.remove('lit');
  });
  ['trigger','state','action','lineage','complete'].forEach(id => {
    const el = document.getElementById(`lv-section-${id}`);
    if (el) el.classList.add('hidden');
  });
  ['i01','i02','i03','i04'].forEach(id => {
    const el = document.getElementById(`lv-infer-${id}`);
    if (el) {
      el.classList.remove('done');
      el.querySelector('.lv-infer-check').textContent = '—';
    }
  });
  ['lv-card-access','lv-card-evac','lv-card-dispatch','lv-card-policy'].forEach(id => {
    document.getElementById(id)?.classList.remove('show');
  });
  const zc = document.getElementById('lv-zone-cards');
  if (zc) zc.innerHTML = '';
  const lc = document.getElementById('lv-lineage-chains');
  if (lc) lc.innerHTML = '';
  const sl = document.getElementById('lv-step-label');
  if (sl) sl.textContent = '';
  lvStep = 0;
  lvRunning = false;  // 이전 실행 잔여 상태 초기화
}

export function mount() {
  store.on('inference:start', () => {
    ['trigger', 'state', 'action', 'lineage', 'llm'].forEach(n => setNodeState(n, null));
    document.querySelectorAll('.pipeline-arrow').forEach(a => a.classList.remove('flowing'));
    setPipelineMessage('파이프라인 시작…');
    setPipelineStatus('IDLE');
    runPipelineSequence();

    // 라이브 뷰 자동 실행 (탭 무관 — 파이프라인 탭에서 결과 확인 가능)
    resetLiveView();
    runLiveView();
  });

  setNodeState('input', 'done');
  setPipelineMessage('추론 재실행 버튼을 눌러 파이프라인을 실행하세요.');

  // 라이브 뷰 버튼 이벤트
  document.getElementById('lv-btn-run')  ?.addEventListener('click', runLiveView);
  document.getElementById('lv-btn-step') ?.addEventListener('click', stepLiveView);
  document.getElementById('lv-btn-reset')?.addEventListener('click', resetLiveView);
}
