import { API_BASE } from '../utils/formatters.js';
import { store } from '../state/store.js';
import { showToast } from '../utils/toast.js';

// timeoutMs: 기본 10초. LLM 브리핑처럼 느린 엔드포인트는 호출 시 별도 지정
export async function safeFetch(path, options = {}, timeoutMs = 10000) {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      signal: AbortSignal.timeout(timeoutMs),
      ...options,
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${path}`);
    return res.json();
  } catch (e) {
    if (e.name === 'TimeoutError' || e.name === 'AbortError') {
      const sec = Math.round(timeoutMs / 1000);
      showToast(`⏱️ 요청 시간 초과 (${sec}s) — 서버 상태 확인`, 'warn');
    } else if (e.message?.includes('Failed to fetch') || e.message?.includes('NetworkError')) {
      showToast('🔌 서버 연결 실패 — TypeDB / FastAPI 기동 여부 확인', 'warn');
    }
    throw e;
  }
}

export async function checkHealth() {
  try {
    const d = await safeFetch('/api/health');
    const badge = document.getElementById('health-badge');
    if (badge) {
      const lmOk  = d.lm_studio?.status === 'connected';
      const lmTag = lmOk ? ' · LM Studio ✓' : '';
      if (d.typedb === 'connected') {
        badge.textContent = `TypeDB 연결됨 · ${d.db_name}${lmTag}`;
        badge.className   = 'text-xs px-2 py-0.5 rounded-full bg-emerald-900/60 text-emerald-400';
      } else {
        badge.textContent = 'TypeDB 연결 실패';
        badge.className   = 'text-xs px-2 py-0.5 rounded-full bg-red-900/60 text-red-400';
      }
    }
    store.set('health', d);
  } catch {
    const badge = document.getElementById('health-badge');
    if (badge) {
      badge.textContent = '서버 오프라인';
      badge.className = 'text-xs px-2 py-0.5 rounded-full bg-slate-700 text-slate-400';
    }
  }
}
