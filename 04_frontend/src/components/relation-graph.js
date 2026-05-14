// 인터랙티브 Relation 그래프 — vis.js Network
// 구간 선택 시 Feature → Signal → State 관계를 노드-엣지로 시각화

import { store } from '../state/store.js';

const NODE_COLORS = {
  segment:     { background: '#6366f1', border: '#818cf8', font: '#fff' },
  feature:     { background: '#059669', border: '#34d399', font: '#fff' },
  signal:      { background: '#92400e', border: '#d97706', font: '#fbbf24' },
  state:       { background: '#991b1b', border: '#ef4444', font: '#fff' },
};

const SIGNAL_WEIGHTS = {
  S_official: '×0.20', S_exposure: '×0.25', S_spread: '×0.20',
  S_action: '×0.20', S_time: '×0.15',
};

const STATE_COLORS = {
  ImmediatePreWatering: '#ef4444',
  PriorityPreWatering:  '#f97316',
  ReviewPreWatering:    '#eab308',
  EnhancedMonitoring:   '#3b82f6',
  GeneralManagement:    '#22c55e',
  NotActionable:        '#6b7280',
};

let network = null;

function buildGraph(detail) {
  if (!detail) return { nodes: [], edges: [] };

  const nodes = [];
  const edges = [];

  // Segment 노드
  nodes.push({
    id: 'seg',
    label: detail.name || detail.segment_id,
    group: 'segment',
    title: `구간 ID: ${detail.segment_id}\nS_priority: ${detail.s_priority}`,
    shape: 'ellipse',
    color: NODE_COLORS.segment,
    font: { color: '#fff', size: 13, bold: true },
    size: 28,
  });

  // Feature 노드
  (detail.features || []).forEach((f, i) => {
    const fid = `feat_${i}`;
    nodes.push({
      id: fid,
      label: f.kind || f.feature_kind,
      group: 'feature',
      title: `Feature: ${f.kind || f.feature_kind}\n점수: ${(f.score || f.feature_score || 0).toFixed(3)}\n클래스: ${f.class || f.feature_class || '-'}`,
      shape: 'box',
      color: NODE_COLORS.feature,
      font: { color: '#fff', size: 11 },
      _meta: { kind: 'Feature', name: f.kind || f.feature_kind, value: f.score || f.feature_score, desc: f.class || f.feature_class },
    });
    edges.push({
      from: 'seg',
      to: fid,
      label: '측정',
      color: { color: '#334155', highlight: '#64748b' },
      font: { color: '#64748b', size: 9, align: 'middle' },
      dashes: false,
      arrows: { to: { enabled: true, scaleFactor: 0.5 } },
    });
  });

  // Signal 노드
  (detail.signals || []).forEach((s, i) => {
    const sid = `sig_${i}`;
    const sname = s.kind || s.signal_kind;
    const weight = SIGNAL_WEIGHTS[sname] || '';
    nodes.push({
      id: sid,
      label: `${sname}\n${weight}`,
      group: 'signal',
      title: `Signal: ${sname}\n점수: ${(s.score || s.signal_score || 0).toFixed(3)}\n가중치: ${weight}`,
      shape: 'diamond',
      color: NODE_COLORS.signal,
      font: { color: '#fbbf24', size: 10 },
      size: 22,
      _meta: { kind: 'Signal', name: sname, value: s.score || s.signal_score, desc: weight },
    });
    // Feature → Signal 엣지 (개념적 연결)
    edges.push({
      from: sid,
      to: 'state',
      label: weight,
      color: { color: '#d97706', highlight: '#fbbf24' },
      font: { color: '#d97706', size: 9, align: 'middle' },
      dashes: [6, 3],
      arrows: { to: { enabled: true, scaleFactor: 0.5 } },
    });
  });

  // Feature → Signal 개념 연결 (스프레드 방식)
  const features = detail.features || [];
  const signals = detail.signals || [];
  features.forEach((f, fi) => {
    // Feature 종류에 따라 관련 Signal로 연결
    const fkind = (f.kind || f.feature_kind || '').toLowerCase();
    signals.forEach((s, si) => {
      const skind = (s.kind || s.signal_kind || '').toLowerCase();
      const related =
        (fkind.includes('risk') && skind.includes('official')) ||
        (fkind.includes('residential') && skind.includes('exposure')) ||
        (fkind.includes('wind') && skind.includes('spread'));
      if (related) {
        edges.push({
          from: `feat_${fi}`,
          to: `sig_${si}`,
          color: { color: '#1e3a2f', highlight: '#059669' },
          font: { size: 8 },
          dashes: false,
          arrows: { to: { enabled: true, scaleFactor: 0.4 } },
        });
      }
    });
  });

  // State 노드
  const stateName = detail.state_band || detail.state || 'Unknown';
  const sp = detail.s_priority ? Number(detail.s_priority).toFixed(3) : '-';
  const ov = detail.override_applied && detail.override_applied !== 'none'
    ? `\nOverride: ${detail.override_applied}` : '';
  const stateColor = STATE_COLORS[stateName] || '#6b7280';
  nodes.push({
    id: 'state',
    label: `${stateName}\nS=${sp}`,
    group: 'state',
    title: `최종 State: ${stateName}\nS_priority: ${sp}${ov}`,
    shape: 'ellipse',
    color: { background: stateColor + '33', border: stateColor, highlight: { background: stateColor + '55', border: stateColor } },
    font: { color: stateColor, size: 12, bold: true },
    size: 32,
    _meta: { kind: 'State', name: stateName, value: sp, desc: ov.replace('\nOverride: ', '') || '기본 State Band' },
  });

  return { nodes, edges };
}

function initNetwork(container, graphData) {
  const options = {
    layout: {
      hierarchical: {
        direction: 'LR',
        sortMethod: 'directed',
        levelSeparation: 180,
        nodeSpacing: 80,
      },
    },
    physics: { enabled: false },
    interaction: {
      hover: true,
      tooltipDelay: 200,
      dragNodes: true,
    },
    edges: {
      smooth: { type: 'cubicBezier', forceDirection: 'horizontal', roundness: 0.4 },
      width: 1.5,
    },
    nodes: {
      borderWidth: 2,
      shadow: { enabled: true, size: 6, color: 'rgba(0,0,0,0.5)' },
    },
  };

  const visNodes = new vis.DataSet(graphData.nodes);
  const visEdges = new vis.DataSet(graphData.edges);

  if (network) { network.destroy(); network = null; }
  network = new vis.Network(container, { nodes: visNodes, edges: visEdges }, options);

  // 노드 클릭 → 상세 표시
  network.on('click', params => {
    if (!params.nodes.length) return;
    const nodeId = params.nodes[0];
    const node = graphData.nodes.find(n => n.id === nodeId);
    if (!node) return;
    const meta = node._meta || {};
    const detail = document.getElementById('graph-node-detail');
    const title  = document.getElementById('graph-node-title');
    const value  = document.getElementById('graph-node-value');
    const desc   = document.getElementById('graph-node-desc');
    if (detail && title && value && desc) {
      title.textContent = `[${meta.kind || ''}] ${meta.name || node.label}`;
      value.textContent = meta.value != null ? String(meta.value) : '';
      desc.textContent  = meta.desc || '';
      detail.classList.remove('hidden');
    }
  });

  return network;
}

export function mount() {
  const container = document.getElementById('relation-graph-vis');
  if (!container) return;

  // 구간 선택 시 그래프 갱신
  store.subscribe('detail', detail => {
    if (!detail) return;
    const segName = document.getElementById('graph-segment-name');
    if (segName) segName.textContent = detail.name || detail.segment_id || '';
    const graphData = buildGraph(detail);
    initNetwork(container, graphData);
  });

  // 초기 detail이 이미 있으면 바로 렌더링
  const existing = store.get('detail');
  if (existing) {
    const graphData = buildGraph(existing);
    initNetwork(container, graphData);
  }
}
