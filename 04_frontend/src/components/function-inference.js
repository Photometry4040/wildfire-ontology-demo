import { store } from '../state/store.js';

// 출력값 하이라이트 여부: S_priority, final_state
const HIGHLIGHT_KEYS = new Set(['S_priority', 'final_state', 'override']);

// TypeQL 키워드 간단 하이라이트 (정규식)
function syntaxHL(code) {
  return code
    .replace(/^(#.*)$/gm, '<span class="cmt">$1</span>')
    .replace(/\b(match|insert|select|let|return|fun|isa|has|or|not)\b/g, '<span class="kw">$1</span>')
    .replace(/"([^"]*)"/g, '<span class="str">"$1"</span>');
}

function buildCard(step, isActive) {
  const card = document.createElement('div');
  card.className = `trace-card${isActive ? ' active' : ''}`;
  card.dataset.step = step.step;

  // 헤더
  const header = document.createElement('div');
  header.className = 'trace-step-label';
  header.textContent = step.label;
  card.appendChild(header);

  // 입력 섹션
  const inputSec = document.createElement('div');
  inputSec.style.cssText = 'margin-bottom:8px;';
  inputSec.innerHTML = '<div style="font-size:10px;color:#475569;margin-bottom:4px;">INPUT</div>';
  step.inputs.forEach(io => {
    const row = document.createElement('div');
    row.className = 'trace-io-row';
    row.innerHTML = `
      <span class="trace-io-key">${io.key}</span>
      <span class="trace-io-value">${typeof io.value === 'number' ? io.value.toFixed(4) : io.value}</span>
    `;
    inputSec.appendChild(row);
  });
  card.appendChild(inputSec);

  // 구분선
  const divider = document.createElement('div');
  divider.style.cssText = 'border-top:1px dashed #334155;margin:8px 0;';
  card.appendChild(divider);

  // 출력 섹션
  const outputSec = document.createElement('div');
  outputSec.innerHTML = '<div style="font-size:10px;color:#475569;margin-bottom:4px;">OUTPUT</div>';
  step.outputs.forEach(io => {
    const row = document.createElement('div');
    row.className = 'trace-io-row';
    const isHL = HIGHLIGHT_KEYS.has(io.key);
    const valStr = typeof io.value === 'number' ? io.value.toFixed(4) : io.value;
    const weightSpan = io.weight ? `<span class="trace-weight">${io.weight}</span>` : '';
    row.innerHTML = `
      <span class="trace-io-key">${io.key}${weightSpan}</span>
      <span class="trace-io-value${isHL ? ' highlight' : ''}">${valStr}</span>
    `;
    outputSec.appendChild(row);
  });
  card.appendChild(outputSec);

  return card;
}

function render(trace) {
  const container = document.getElementById('fn-inference-container');
  if (!container) return;

  if (!trace) {
    container.innerHTML = '<div class="text-slate-600 text-sm text-center py-6">구간을 선택하면 추론 trace가 표시됩니다.</div>';
    return;
  }

  container.innerHTML = '';

  // 카드 행 + 코드 뷰
  const cardRow = document.createElement('div');
  cardRow.className = 'flex items-start gap-2 overflow-x-auto pb-2';
  cardRow.id = 'fn-card-row';

  const codeArea = document.createElement('div');
  codeArea.id = 'fn-code-area';
  codeArea.style.cssText = 'display:none;';

  let activeStep = null;

  trace.steps.forEach((step, i) => {
    // 카드
    const card = buildCard(step, false);
    card.addEventListener('click', () => {
      // 활성 토글
      if (activeStep === step.step) {
        activeStep = null;
        card.classList.remove('active');
        codeArea.style.display = 'none';
        return;
      }
      document.querySelectorAll('#fn-card-row .trace-card').forEach(c => c.classList.remove('active'));
      card.classList.add('active');
      activeStep = step.step;

      codeArea.style.display = 'block';
      codeArea.innerHTML = `
        <pre class="trace-code-block">${syntaxHL(step.typeql_snippet)}</pre>
        ${step.formula_note ? `<div class="trace-formula-note">💡 ${step.formula_note}</div>` : ''}
      `;
    });
    cardRow.appendChild(card);

    // 화살표 (마지막 카드 제외)
    if (i < trace.steps.length - 1) {
      const arrow = document.createElement('div');
      arrow.className = 'trace-arrow';
      arrow.textContent = '→';
      cardRow.appendChild(arrow);
    }
  });

  container.appendChild(cardRow);
  container.appendChild(codeArea);
}

export function mount() {
  store.subscribe('inferenceTrace', render);
}
