// app.js — 재난 온톨로지 추론 엔진 라이브 데모
// API 베이스: FastAPI localhost:8001

const API = 'http://localhost:8001/api/baseline';

// ─── 상태 ───────────────────────────────────────────────────────
let currentStep = 0; // 0=idle, 1=trigger, 2=state, 3=action, 4=lineage
let running     = false;

// ─── 헬퍼 ───────────────────────────────────────────────────────
function toast(msg, type = 'info') {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = `show ${type}`;
  clearTimeout(el._t);
  el._t = setTimeout(() => { el.className = ''; }, 3200);
}

function setMsg(msg) {
  document.getElementById('pipeline-msg').textContent = msg;
}

function setPhase(id, state) {
  const el = document.getElementById(`phase-${id}`);
  if (!el) return;
  el.className = `phase-step ${state}`;
  const status = el.querySelector('.phase-status');
  if (status) status.textContent = state.toUpperCase();
}

function litArrow(n) {
  const el = document.getElementById(`arrow-${n}`);
  if (el) el.classList.add('lit');
}

function show(sectionId) {
  const el = document.getElementById(`section-${sectionId}`);
  if (el) el.classList.remove('hidden');
}

function setLock(locked) {
  running = locked;
  document.getElementById('btn-run').disabled  = locked;
  document.getElementById('btn-step').disabled = locked;
  document.getElementById('btn-reset').disabled = locked;
}

function wait(ms) { return new Promise(r => setTimeout(r, ms)); }

// ─── DB 상태 표시 ────────────────────────────────────────────────
function setDbStatus(ok) {
  const el = document.getElementById('db-status');
  el.textContent = ok ? 'DB 초기화 완료' : 'DB 미초기화';
  el.className = `text-xs px-2 py-1 rounded-full ${
    ok ? 'bg-green-900/40 text-green-400' : 'bg-slate-800 text-slate-400'
  }`;
}

// ─── Phase 0+1: 초기화 + Trigger ─────────────────────────────────
async function runTrigger() {
  setPhase('trigger', 'running');
  setMsg('Phase 0: DB 초기화 중…');
  toast('onto-fire DB 재생성 + 스키마 로드 중…');

  const initRes = await fetch(`${API}/init`, { method: 'POST' });
  if (!initRes.ok) throw new Error('DB 초기화 실패');
  setDbStatus(true);
  await wait(600);

  setMsg('Phase 1: 고위험 구역 감지 중…');
  toast('위험지수 Threshold 비교 중…');

  const res = await fetch(`${API}/trigger`);
  if (!res.ok) throw new Error('Trigger 조회 실패');
  const data = await res.json();

  renderZoneCards(data.high_risk_zones, data.weather);
  show('trigger');
  setPhase('trigger', 'done');
  litArrow(1);
  setMsg('Phase 1 완료 — 고위험 구역 감지됨');
  toast(`구역 ${data.high_risk_zones.length}개 감지 (임계 초과: ${data.high_risk_zones.filter(z => z.critical).length}개)`, 'done');
  currentStep = 1;
}

function renderZoneCards(zones, weather) {
  const container = document.getElementById('zone-cards');
  container.innerHTML = '';
  const weatherMap = {};
  weather.forEach(w => { weatherMap[w.zone] = w; });

  // 모든 구역 표시 (위험/정상 포함)
  const allZones = [...new Set([...zones.map(z => z.zone), ...weather.map(w => w.zone)])];
  allZones.forEach(zoneName => {
    const risk = zones.find(z => z.zone === zoneName);
    const wx   = weatherMap[zoneName] || {};
    const isCritical = risk?.critical;
    const isWarning  = risk && !isCritical;
    const cls = isCritical ? 'critical' : isWarning ? 'warning' : 'normal';
    const ri  = risk?.risk_index ?? 0;
    const gaugeColor = isCritical ? '#ef4444' : isWarning ? '#eab308' : '#22c55e';

    const card = document.createElement('div');
    card.className = `zone-card ${cls}`;
    card.innerHTML = `
      <div class="flex items-center justify-between mb-2">
        <div class="text-sm font-bold text-slate-200">${zoneName}</div>
        ${isCritical ? '<span class="text-xs px-2 py-0.5 rounded-full bg-red-900/50 text-red-400">🚨 임계 초과</span>' :
          isWarning  ? '<span class="text-xs px-2 py-0.5 rounded-full bg-yellow-900/40 text-yellow-400">⚠️ 경계</span>' :
                       '<span class="text-xs px-2 py-0.5 rounded-full bg-green-900/30 text-green-400">✅ 정상</span>'}
      </div>
      ${risk ? `
        <div class="text-xs text-slate-400 mb-1">위험지수 <span class="font-mono text-slate-200 font-bold">${ri.toFixed(2)}</span></div>
        <div class="gauge-bar"><div class="gauge-fill" style="width:${ri*100}%;background:${gaugeColor};"></div></div>
        <div class="text-xs text-slate-500 mt-1">위험등급: ${risk.risk_level}</div>
      ` : '<div class="text-xs text-slate-600">위험 데이터 없음</div>'}
      ${wx.humidity != null ? `
        <div class="mt-2 flex gap-3 text-xs">
          <span class="${wx.dry ? 'text-red-400' : 'text-slate-400'}">💧 ${wx.humidity}% ${wx.dry ? '건조' : ''}</span>
          <span class="${wx.strong_wind ? 'text-orange-400' : 'text-slate-400'}">💨 ${wx.wind_speed} m/s ${wx.strong_wind ? '강풍' : ''}</span>
        </div>
      ` : ''}
    `;
    container.appendChild(card);
  });
}

// ─── Phase 2: 추론 INSERT ─────────────────────────────────────────
async function runInference() {
  setPhase('state', 'running');
  show('state');
  setMsg('Phase 2: 추론 INSERT 실행 중… (i01~i04)');

  // i01~i04 순차 체크마크 (애니메이션 효과)
  const steps = ['i01', 'i02', 'i03', 'i04'];
  for (const s of steps) {
    const el = document.getElementById(`infer-${s}`);
    if (el) { el.querySelector('.infer-check').textContent = '⟳'; }
    await wait(300);
  }

  const res = await fetch(`${API}/infer`, { method: 'POST' });
  if (!res.ok) throw new Error('추론 INSERT 실패');
  await res.json();

  // 완료 마크
  for (const s of steps) {
    const el = document.getElementById(`infer-${s}`);
    if (el) {
      el.classList.add('done');
      el.querySelector('.infer-check').textContent = '✓';
      await wait(250);
    }
  }

  setPhase('state', 'done');
  litArrow(2);
  setMsg('Phase 2 완료 — i01~i04 TypeDB INSERT 성공');
  toast('추론 완료: 결정 엔티티 4종이 TypeDB에 생성됨', 'done');
  currentStep = 2;
}

// ─── Phase 3: ACTION ─────────────────────────────────────────────
async function runActions() {
  setPhase('action', 'running');
  show('action');
  setMsg('Phase 3: 결정 결과 조회 중…');

  const res = await fetch(`${API}/actions`);
  if (!res.ok) throw new Error('Action 조회 실패');
  const data = await res.json();

  // 접근통제
  document.getElementById('action-access').innerHTML =
    data.access_control.length
      ? data.access_control.map(a => `<div class="flex items-center gap-1 mb-1"><span class="text-red-400">■</span> ${a.zone} 출입 통제</div>`).join('')
      : '<span class="text-slate-600">해당 없음</span>';

  // 대피경보
  document.getElementById('action-evac').innerHTML =
    data.evacuation.length
      ? data.evacuation.map(e => `<div class="mb-1">🏘️ ${e.incident} → <span class="text-amber-300">${e.settlement}</span> 대피경보</div>`).join('')
      : '<span class="text-slate-600">해당 없음</span>';

  // 출동
  document.getElementById('action-dispatch').innerHTML =
    data.dispatch.length
      ? data.dispatch.map(d => `<div class="mb-1">🚒 ${d.crew} + ${d.engine} + ${d.aircraft}</div>`).join('')
      : '<span class="text-slate-600">해당 없음</span>';

  // 정책권고
  document.getElementById('action-policy').innerHTML =
    data.policy.length
      ? data.policy.map(p => `<div class="mb-1">📋 ${p.incident} → 보고 ${p.report_at} → 정책권고 생성</div>`).join('')
      : '<span class="text-slate-600">해당 없음</span>';

  // 카드 팝업 애니메이션
  await wait(100);
  ['card-access', 'card-evac', 'card-dispatch', 'card-policy'].forEach((id, i) => {
    setTimeout(() => document.getElementById(id)?.classList.add('show'), i * 150);
  });

  setPhase('action', 'done');
  litArrow(3);
  setMsg('Phase 3 완료 — 4개 결정 생성됨');
  toast('접근통제 · 대피경보 · 출동 · 정책권고 확인', 'done');
  currentStep = 3;
}

// ─── Phase 4: LINEAGE ─────────────────────────────────────────────
async function runLineage() {
  setPhase('lineage', 'running');
  show('lineage');
  setMsg('Phase 4: 결정 근거 역추적 중…');

  const res = await fetch(`${API}/lineage`);
  if (!res.ok) throw new Error('Lineage 조회 실패');
  const data = await res.json();

  renderLineageChains(data.lineage);

  setPhase('lineage', 'done');
  setMsg('Phase 4 완료 — "왜 이 결정인가?" 역추적 완료');
  toast('Lineage 역추적 완료 — 3종 근거 시각화', 'done');
  currentStep = 4;

  // 완료 배너
  await wait(400);
  show('complete');
}

function renderLineageChains(lineage) {
  const container = document.getElementById('lineage-chains');
  container.innerHTML = '';

  lineage.forEach((item, idx) => {
    const chain = document.createElement('div');
    chain.className = 'rounded-xl border border-slate-800 p-4';
    chain.style.background = '#0f172a';

    const { dry, strong_wind, low_fuel_moisture } = item.triggers;
    const isHigh = item.risk_index >= 0.85;

    chain.innerHTML = `
      <div class="text-xs font-semibold text-slate-400 mb-3 uppercase tracking-wider">
        ${item.zone} — ${item.decision}
      </div>
      <div class="flex items-center gap-2 flex-wrap">
        <!-- 노드 1: 위험지수 -->
        <div class="lineage-node ${isHigh ? 'lit' : ''}" title="위험지수 임계 초과 여부">
          <div class="text-xs text-slate-500 mb-1">위험지수</div>
          <div class="font-mono font-bold ${isHigh ? 'text-red-400' : 'text-slate-300'}">${item.risk_index.toFixed(2)}</div>
          <div class="text-xs mt-1 ${isHigh ? 'text-red-400' : 'text-slate-500'}">${item.risk_level}</div>
        </div>
        <div class="lineage-arrow ${isHigh ? 'lit' : ''}">→</div>
        <!-- 노드 2: 기상 -->
        <div class="lineage-node ${(dry || strong_wind) ? 'lit' : ''}" title="기상 조건">
          <div class="text-xs text-slate-500 mb-1">기상</div>
          <div class="text-xs ${dry ? 'text-orange-400' : 'text-slate-400'}">💧 ${item.humidity}% ${dry ? '⚠️' : ''}</div>
          <div class="text-xs ${strong_wind ? 'text-orange-400' : 'text-slate-400'}">💨 ${item.wind_speed}m/s ${strong_wind ? '⚠️' : ''}</div>
        </div>
        <div class="lineage-arrow ${(dry || strong_wind) ? 'lit' : ''}">→</div>
        <!-- 노드 3: 연료수분 -->
        <div class="lineage-node ${low_fuel_moisture ? 'lit' : ''}" title="연료수분">
          <div class="text-xs text-slate-500 mb-1">연료수분</div>
          <div class="font-mono font-bold ${low_fuel_moisture ? 'text-red-400' : 'text-slate-300'}">${item.fuel_moisture}%</div>
          <div class="text-xs mt-1 ${low_fuel_moisture ? 'text-red-400' : 'text-slate-500'}">${low_fuel_moisture ? '발화위험 🔥' : '정상'}</div>
        </div>
        <div class="lineage-arrow ${isHigh ? 'lit' : ''}">→</div>
        <!-- 노드 4: 결정 -->
        <div class="lineage-node ${isHigh ? 'lit' : ''}" style="${isHigh ? 'border-color:#f59e0b;background:rgba(245,158,11,0.08);' : ''}">
          <div class="text-xs text-slate-500 mb-1">결정</div>
          <div class="text-xs font-bold ${isHigh ? 'text-amber-300' : 'text-slate-400'}">${item.decision}</div>
          <div class="text-xs mt-1 text-slate-500">${isHigh ? '★ 추론 생성' : '모니터링'}</div>
        </div>
      </div>
      <div class="mt-2 text-xs text-slate-600">
        Trigger 조건 충족:
        ${isHigh ? '<span class="text-red-400 mr-2">위험지수≥0.85 ✓</span>' : ''}
        ${dry ? '<span class="text-orange-400 mr-2">건조(습도<30%) ✓</span>' : ''}
        ${strong_wind ? '<span class="text-orange-400 mr-2">강풍(>7m/s) ✓</span>' : ''}
        ${low_fuel_moisture ? '<span class="text-red-400 mr-2">연료수분<10% ✓</span>' : ''}
      </div>
    `;

    // 노드 순차 점등 애니메이션
    setTimeout(() => {
      chain.querySelectorAll('.lineage-node').forEach((n, i) => {
        setTimeout(() => n.classList.add('lit'), i * 200);
      });
    }, idx * 300);

    container.appendChild(chain);
  });
}

// ─── 전체 파이프라인 순차 실행 ────────────────────────────────────
async function runFullPipeline() {
  if (running) return;
  setLock(true);
  resetUI();
  try {
    await runTrigger();  await wait(800);
    await runInference(); await wait(800);
    await runActions();   await wait(800);
    await runLineage();
  } catch (e) {
    toast(`오류: ${e.message}`, 'err');
    console.error(e);
  } finally {
    setLock(false);
  }
}

// ─── 단계별 실행 ──────────────────────────────────────────────────
async function runNextStep() {
  if (running) return;
  setLock(true);
  try {
    if (currentStep === 0) { await runTrigger(); }
    else if (currentStep === 1) { await runInference(); }
    else if (currentStep === 2) { await runActions(); }
    else if (currentStep === 3) { await runLineage(); }
    else { toast('모든 단계가 완료되었습니다. 초기화 후 다시 시작하세요.'); }
  } catch (e) {
    toast(`오류: ${e.message}`, 'err');
    console.error(e);
  } finally {
    setLock(false);
    const labels = ['', '⏭ 단계 2: 추론 INSERT', '⏭ 단계 3: 결정 결과', '⏭ 단계 4: Lineage', '✅ 완료'];
    document.getElementById('step-label').textContent = labels[currentStep] || '';
  }
}

// ─── UI 초기화 ────────────────────────────────────────────────────
function resetUI() {
  ['trigger','state','action','lineage'].forEach(p => setPhase(p, 'idle'));
  [1,2,3].forEach(n => {
    const el = document.getElementById(`arrow-${n}`);
    if (el) el.classList.remove('lit');
  });
  ['trigger','state','action','lineage','complete'].forEach(s => {
    const el = document.getElementById(`section-${s}`);
    if (el) el.classList.add('hidden');
  });
  ['i01','i02','i03','i04'].forEach(id => {
    const el = document.getElementById(`infer-${id}`);
    if (el) {
      el.classList.remove('done');
      el.querySelector('.infer-check').textContent = '—';
    }
  });
  ['card-access','card-evac','card-dispatch','card-policy'].forEach(id => {
    document.getElementById(id)?.classList.remove('show');
  });
  document.getElementById('zone-cards').innerHTML = '';
  document.getElementById('lineage-chains').innerHTML = '';
  document.getElementById('step-label').textContent = '';
  setMsg('추론 시작 버튼을 눌러주세요');
  currentStep = 0;
}

async function resetAll() {
  resetUI();
  setDbStatus(false);
  toast('초기화 완료 — 추론 시작을 눌러 다시 실행하세요');
}
