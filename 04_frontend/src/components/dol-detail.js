// B-5: 8축 DOL 상세 오버레이
// 각 축의 정의·구현 상태·발표 인용을 담은 콘텐츠 맵

const AXIS_META = {
  application: { icon: '🖥️', name: 'Application', sub: '화면 · workflow · UI 흐름' },
  decision:    { icon: '⚖️', name: 'Decision',    sub: '5 Gate · 9 Override · 의사결정 엔진' },
  data:        { icon: '🗃️', name: 'Data',        sub: 'Raw → Backing → Ontology 3계층' },
  logic:       { icon: '🧠', name: 'Logic',       sub: '함수 추론 · 5 Signal · S_priority 공식' },
  action:      { icon: '🎯', name: 'Action',      sub: 'PreWatering 자원 배정 · State별 권고' },
  security:    { icon: '🔐', name: 'Security',    sub: '접근 권한 · 감사 로그 (Phase 2)' },
  feedback:    { icon: '🔁', name: 'Feedback',    sub: 'Lineage 역추적 · Audit trail' },
  operations:  { icon: '📊', name: 'Operations',  sub: '임계치 · 모니터링 주기 · 운영 현황' },
};

function badge(type, text) {
  return `<span class="dol-badge ${type}">${text}</span>`;
}

function table(headers, rows) {
  const ths = headers.map(h => `<th>${h}</th>`).join('');
  const trs = rows.map(r =>
    `<tr>${r.map(c => `<td>${c}</td>`).join('')}</tr>`
  ).join('');
  return `<table class="dol-table"><thead><tr>${ths}</tr></thead><tbody>${trs}</tbody></table>`;
}

function code(text) {
  return `<div class="dol-code">${text}</div>`;
}

// ── 8개 축 콘텐츠 ──────────────────────────────────────────

const CONTENT = {

  application: () => `
    <div class="dol-section">
      <h3>구현된 UI 패널 목록 ${badge('done', '✅ 완료')}</h3>
      ${table(
        ['패널', '기능', 'Phase'],
        [
          ['🔄 파이프라인 라이브뷰', 'Trigger→State→Action→Lineage→LLM 시퀀스', 'A'],
          ['📚 3계층 아키텍처', 'Raw→Backing→Ontology 흐름 + 예제 토글', 'A'],
          ['🕸️ Relation 그래프', '실선(Raw) vs 점선(추론) SVG 시각화', 'A'],
          ['🔥 LLM 브리핑', 'Gemini 한국어 보고서 + 상위 5개 구간', 'A'],
          ['📋 구간 목록', 'S_priority 바 + State 배지', 'A'],
          ['🔬 함수 추론 3단계', 'calc_features→calc_signals→decide + TypeQL 코드', 'B-4'],
          ['📈 State vs Status', 'State 설명 카드 + 6단계 타임라인', 'B-1'],
          ['🎚️ 가중치 시뮬레이터', '5 Signal 가중치 조정 → Before/After', 'B-3'],
          ['🌐 S/K 모드 전환', 'Semantic(의미)/Kinetic(동작) 강조', 'B-2'],
          ['8축 DOL 상세', '이 화면', 'B-5'],
        ]
      )}
    </div>
    <div class="dol-section">
      <h3>발표 인용</h3>
      <p style="font-size:13px;color:#94a3b8;line-height:1.6;">
        "화면 한 장에 발화·진압·복귀 의사결정 사이클이 모두 담겨 있습니다. 클릭 한 번으로 다음 행동을 알 수 있습니다."
      </p>
    </div>
  `,

  decision: () => `
    <div class="dol-section">
      <h3>5 Decision Gate ${badge('done', '✅ Reasoning')}</h3>
      ${table(
        ['#', 'Gate 이름', '발동 조건', '모드'],
        [
          ['1', 'SelectPreWateringSegment', 'State ≥ ReviewPreWatering', 'advisory_only'],
          ['2', 'SchedulePreWatering', 'Select + S_time 확보', 'advisory_only (F_time_lead=low)'],
          ['3', 'AssignResourcePackage', 'Schedule + 자원 가용성', 'manual_review (미구현 2개↑)'],
          ['4', 'DeferOrMonitor', 'MonitorOnly / NotActionable', 'advisory_only (safety=low)'],
          ['5', 'RequestManualReview', 'mock_input, join 실패, 상위 State', 'manual_review'],
        ]
      )}
    </div>
    <div class="dol-section">
      <h3>9 Override 우선순위 (높음→낮음)</h3>
      ${table(
        ['순위', 'Override', '조건', '결과 State'],
        [
          ['1', 'HazardGate', 'hazard-flag = true', 'NotActionable'],
          ['2', 'AccessGate', 'infeasible_dispatch or vehicle 불가', 'Deferred'],
          ['3', 'RainGate', 'RainOffset > 0.6', 'MonitorOnly'],
          ['4', 'Recheck', 'previous_completed + 새 위험창', 'Recheck'],
          ['5', 'Completed', 'previous_completed (위험창 없음)', 'Completed'],
          ['6', 'AlertSevere', 'alert_class = 경보', 'min PriorityPreWatering'],
          ['7', 'AlertWarning', 'alert_class = 주의보 + S_exposure ≥ 0.5', 'min ReviewPreWatering'],
          ['8 ★', 'GradeSevere', 'risk_grade = 매우높음 or index ≥ 86', 'min PriorityPreWatering'],
          ['9', 'GradeHigh', 'risk_grade = 높음 or index ≥ 66', 'min ReviewPreWatering'],
        ]
      )}
      <p style="font-size:11px;color:#475569;margin-top:8px;">★ 곡성 SEG-JN-C에 실제 적용: sp=0.4625(Review) → GradeSevere → PriorityPreWatering</p>
    </div>
  `,

  data: () => `
    <div class="dol-section">
      <h3>L1 Raw — 외부 API 원본 ${badge('done', '✅')}</h3>
      ${code(`{"region": "곡성군", "sigucode": "4672000000",\n "risk_level": "매우높음", "risk_index": 91.0,\n "wind_speed": 14.2, "wind_dir": "NW"}`)}
      <p style="font-size:11px;color:#475569;">출처: 산림청 OpenAPI · KMA 기상자료 · FGIS 지리정보</p>
    </div>
    <div class="dol-section">
      <h3>L2 Backing — 정규화 + 캐싱 ${badge('done', '✅')}</h3>
      ${code(`{segment_id: "SEG-JN-C", segment_name: "전남 담양군 추월산 C구간",\n risk_score: 1.00, wind_norm: 0.71,\n residential_exposure: 0.35, s_spread_mock: 0.55,\n ts: "2025-01-21T08:00:00"}`)}
      <p style="font-size:11px;color:#475569;">pydantic dataclass · SQLite 캐시 · 시간 정렬</p>
    </div>
    <div class="dol-section">
      <h3>L3 Ontology — 추론된 관계 ${badge('done', '✅ TypeDB')}</h3>
      ${code(`$seg isa pre-watering-segment, has segment-id "SEG-JN-C";\n$fr isa feature-record, has feature-kind "FireRiskLevel", has feature-score 1.00;\n(subject: $seg, result: $fr) isa segment-feature;\n\n# compute_s_priority() TypeQL 함수 → s-priority 0.4625\n# GradeSevere Override → decision-state "PriorityPreWatering"`)}
    </div>
  `,

  logic: () => `
    <div class="dol-section">
      <h3>S_priority 공식 ${badge('done', '✅')}</h3>
      ${code(`S_priority = 0.20 × S_official\n           + 0.25 × S_exposure   ← 가장 큰 가중치 (보호 대상 우선)\n           + 0.20 × S_spread\n           + 0.20 × S_action\n           + 0.15 × S_time`)}
    </div>
    <div class="dol-section">
      <h3>5 Signal 공식</h3>
      ${table(
        ['Signal', '공식 (가중합)', '상태'],
        [
          ['S_official', 'FireRiskLevel×0.40 + Trend×0.20 + Alert×0.40', badge('done','✅')],
          ['S_exposure', 'ResidentialExposure×0.40 + CriticalAsset×0.35 + ForestInterface×0.25', badge('done','✅')],
          ['S_spread', 'WindTowardAsset×0.40 + Terrain×0.25 + FuelContinuity×0.35', badge('done','✅')],
          ['S_action', 'WateringActionability (stub 0.5)', badge('warn','⚠️ C-1 stub')],
          ['S_time', 'HighRiskWindow×0.35 + RainOffset×0.20', badge('done','✅')],
        ]
      )}
    </div>
    <div class="dol-section">
      <h3>5 State Band</h3>
      ${table(
        ['S_priority 범위', 'State'],
        [
          ['≥ 0.80', '🔴 ImmediatePreWatering'],
          ['0.60 ~ 0.80', '🟠 PriorityPreWatering'],
          ['0.40 ~ 0.60', '🟡 ReviewPreWatering'],
          ['0.20 ~ 0.40', '🔵 EnhancedMonitoring'],
          ['< 0.20', '🟢 GeneralManagement'],
        ]
      )}
    </div>
  `,

  action: () => `
    <div class="dol-section">
      <h3>State별 권고 Action ${badge('warn', '⚠️ Mock')}</h3>
      ${table(
        ['State', '권고 Action'],
        [
          ['🔴 ImmediatePreWatering', '즉시 출동·주수·완료기록·재점검 예약'],
          ['🟠 PriorityPreWatering', '예정 출동·주수·완료기록'],
          ['🟡 ReviewPreWatering', '관할청 통보·일일 재점검 예약'],
          ['🔵 EnhancedMonitoring', '일 2회 재점검 예약'],
          ['🟢 GeneralManagement', '조치 없음'],
          ['⛔ NotActionable', '안전 위험 통보·위험 해소 후 재점검'],
          ['🌧️ MonitorOnly', '강수 종료 후 재점검 예약'],
          ['⏸ Deferred', '접근 차단 통보·접근 복구 후 재점검'],
        ]
      )}
    </div>
    <div class="dol-section">
      <h3>현재 구현 한계 & 로드맵</h3>
      <p style="font-size:12px;color:#94a3b8;line-height:1.6;">
        현재는 <strong style="color:#fbbf24;">Action 권고</strong>만 출력합니다. 실제 자원 배정(차량·인력 스케줄링)은
        <strong>AssignResourcePackage Gate</strong> 구현 완료 시 연계 가능합니다.<br><br>
        S_action signal이 stub(0.5) 상태이므로 WateringActionability Feature 구현 후
        자동 자원 배정으로 업그레이드 예정입니다.
      </p>
    </div>
  `,

  security: () => `
    <div class="dol-section">
      <h3>구현 상태 ${badge('plan', '⬜ Phase 2')}</h3>
      <p style="font-size:12px;color:#94a3b8;line-height:1.6;">
        Security 축은 현재 미구현입니다. 다음 Phase에서 TypeDB RBAC로 구현 예정입니다.
      </p>
    </div>
    <div class="dol-section">
      <h3>Phase 2 설계 (예정)</h3>
      ${table(
        ['역할', '권한'],
        [
          ['관리자', '전체 읽기/쓰기 + 설정 변경'],
          ['현장지휘관', '구간 결정 승인/거부 + Lineage 조회'],
          ['모니터링요원', '읽기 전용 + 재점검 예약'],
          ['분석가', '읽기 전용 + 임계치 시뮬레이션'],
        ]
      )}
    </div>
    <div class="dol-section">
      <h3>TypeDB RBAC 개요 (예정)</h3>
      ${code(`# TypeDB 역할 기반 접근 제어 (Phase 2 설계)\ndefine\n  role admin;\n  role field-commander;\n  role monitor;\n  entity user, plays access-control:user;\n  relation access-control,\n    relates user, relates target, relates role;`)}
    </div>
  `,

  feedback: () => `
    <div class="dol-section">
      <h3>Lineage 개념 ${badge('done', '✅ Audit')}</h3>
      <p style="font-size:12px;color:#94a3b8;line-height:1.6;">
        모든 의사결정에 역추적 가능한 근거 체인을 유지합니다.<br>
        <strong style="color:#e2e8f0;">Feature × Signal → S_priority → State</strong><br>
        "왜 곡성이 1위인가?"에 수치 기반으로 답할 수 있습니다.
      </p>
    </div>
    <div class="dol-section">
      <h3>역추적 경로 예시 (SEG-JN-C)</h3>
      ${table(
        ['특징', '특징점수', '신호', '신호점수', 'S_priority', '최종 State'],
        [
          ['화재위험수준', '1.0000', 'S_official (×0.20)', '0.5000', '0.4625', 'PriorityPreWatering [GradeSevere]'],
          ['주거노출도', '0.3500', 'S_exposure (×0.25)', '0.3500', '0.4625', '—'],
          ['자산방향풍속', '0.6500', 'S_spread (×0.20)', '0.5500', '0.4625', '—'],
        ]
      )}
    </div>
    <div class="dol-section">
      <h3>API 엔드포인트</h3>
      ${code(`GET /api/segments/{id}/lineage\n→ [ { feature_kind, feature_score, signal_kind,\n      signal_score, s_priority, state_band,\n      override_applied }, ... ]\n\nGET /api/segments/{id}/inference-trace\n→ { steps: [ calc_features, calc_signals, decide ] }`)}
    </div>
  `,

  operations: () => `
    <div class="dol-section">
      <h3>임계치 현황 ${badge('warn', '⚠️ 부분')}</h3>
      ${table(
        ['임계치', '값', '적용'],
        [
          ['S_priority → ImmediatePreWatering', '≥ 0.80', '✅'],
          ['S_priority → PriorityPreWatering', '≥ 0.60', '✅'],
          ['S_priority → ReviewPreWatering', '≥ 0.40', '✅'],
          ['S_priority → EnhancedMonitoring', '≥ 0.20', '✅'],
          ['GradeSevere 발동 (위험지수)', '≥ 86.0', '✅'],
          ['GradeSevere 발동 (등급)', '매우높음', '✅'],
          ['RainGate 발동 (강수 점수)', '> 0.60', '✅'],
          ['AlertWarning 발동 (S_exposure)', '≥ 0.50', '✅'],
        ]
      )}
    </div>
    <div class="dol-section">
      <h3>모니터링 주기 (권장)</h3>
      ${table(
        ['작업', '주기', '상태'],
        [
          ['추론 재실행 (전체)', '일 1회 (새벽 6시)', badge('warn','⚠️ 수동')],
          ['LLM 브리핑 생성', '일 1회 (localStorage 캐시)', badge('done','✅')],
          ['산림청 API 데이터 갱신', '6시간마다 (실데이터 연결 시)', badge('plan','⬜ 미연결')],
          ['KMA 기상 갱신', '3시간마다', badge('plan','⬜ 미연결')],
          ['Lineage 정리', '7일 보존 (예정)', badge('plan','⬜ Phase 2')],
        ]
      )}
    </div>
    <div class="dol-section">
      <h3>가중치 시뮬레이터 연동</h3>
      <p style="font-size:12px;color:#94a3b8;line-height:1.6;">
        S_priority 가중치 슬라이더(B-3)로 임계치 민감도를 실시간 시뮬레이션할 수 있습니다.<br>
        예: S_exposure 0.25→0.40 변경 시 보호 구역 우선순위 변화 관찰 가능.
      </p>
    </div>
  `,
};

// ── 오버레이 로직 ──

function openOverlay(axisKey) {
  const meta = AXIS_META[axisKey];
  if (!meta) return;

  document.getElementById('dol-ov-icon').textContent = meta.icon;
  document.getElementById('dol-ov-name').textContent = meta.name;
  document.getElementById('dol-ov-sub').textContent  = meta.sub;
  document.getElementById('dol-ov-body').innerHTML   = (CONTENT[axisKey] ?? (() => '<p>준비 중</p>'))();

  const overlay = document.getElementById('dol-overlay');
  overlay.classList.add('open');
  overlay.scrollTop = 0;
  document.body.style.overflow = 'hidden';
}

function closeOverlay() {
  document.getElementById('dol-overlay')?.classList.remove('open');
  document.body.style.overflow = '';
}

export function mount() {
  // 8개 카드에 클릭 이벤트
  document.querySelectorAll('.dol-axis').forEach(card => {
    const name = card.querySelector('.dol-name')?.textContent?.toLowerCase();
    if (!name) return;
    card.addEventListener('click', () => openOverlay(name));
  });

  // 닫기 버튼
  document.getElementById('dol-ov-close')?.addEventListener('click', closeOverlay);

  // 배경 클릭 닫기
  document.getElementById('dol-overlay')?.addEventListener('click', e => {
    if (e.target.id === 'dol-overlay') closeOverlay();
  });

  // ESC 키
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && document.getElementById('dol-overlay')?.classList.contains('open')) {
      closeOverlay();
    }
  });
}
