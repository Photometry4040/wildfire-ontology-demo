import Chart from 'chart.js/auto';
import { store } from '../state/store.js';
import { STATE_KR, FEATURE_LABEL, SIGNAL_LABEL, OVERRIDE_LABEL } from '../utils/formatters.js';

let chartFeatures = null;
let chartSignals  = null;

function renderBarChart(canvasId, labels, data, colors) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  if (canvasId === 'chart-features' && chartFeatures) { chartFeatures.destroy(); chartFeatures = null; }
  if (canvasId === 'chart-signals'  && chartSignals)  { chartSignals.destroy();  chartSignals  = null; }

  const chart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{ data, backgroundColor: colors, borderRadius: 4, borderSkipped: false }],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: ctx => ` ${ctx.parsed.y.toFixed(4)}` } },
      },
      scales: {
        x: { ticks: { color: '#94a3b8', font: { size: 10 } }, grid: { color: '#1e293b' } },
        y: { min: 0, max: 1, ticks: { color: '#94a3b8', font: { size: 10 }, stepSize: 0.25 }, grid: { color: '#334155' } },
      },
    },
  });

  if (canvasId === 'chart-features') chartFeatures = chart;
  else chartSignals = chart;
}

function render(d) {
  if (!d) return;

  const placeholder = document.getElementById('detail-placeholder');
  const panel       = document.getElementById('detail-panel');
  if (placeholder) placeholder.classList.add('hidden');
  if (panel)       panel.classList.remove('hidden');

  document.getElementById('d-name').textContent = d.segment_name;

  const stateBadge = document.getElementById('d-state-badge');
  stateBadge.textContent = STATE_KR[d.state_band] ?? d.state_band;
  stateBadge.className   = `state-badge state-${d.state_band}`;

  const ovBadge = document.getElementById('d-override-badge');
  if (d.override_applied && d.override_applied !== 'none') {
    ovBadge.textContent = OVERRIDE_LABEL[d.override_applied] ?? d.override_applied;
    ovBadge.classList.remove('hidden');
  } else {
    ovBadge.classList.add('hidden');
  }

  document.getElementById('d-sp').textContent    = d.s_priority.toFixed(4);
  document.getElementById('d-grade').textContent = d.risk_grade;
  document.getElementById('d-ri').textContent    = d.risk_index.toFixed(1);
  document.getElementById('d-hf').textContent    = d.hazard_flag ? '위험' : '정상';
  document.getElementById('d-hf').style.color    = d.hazard_flag ? '#ef4444' : '#22c55e';

  renderBarChart('chart-features',
    d.features.map(f => FEATURE_LABEL[f.kind] ?? f.kind),
    d.features.map(f => f.score),
    ['#38bdf8', '#818cf8', '#fb7185'],
  );

  renderBarChart('chart-signals',
    d.signals.map(s => SIGNAL_LABEL[s.kind] ?? s.kind),
    d.signals.map(s => s.score),
    ['#34d399', '#a78bfa'],
  );
}

export function mount() {
  store.subscribe('detail', render);
  // inferenceTrace는 function-inference.js가 별도 구독
}
