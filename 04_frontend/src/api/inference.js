import { safeFetch } from './client.js';
import { store } from '../state/store.js';
import { showToast } from '../utils/toast.js';

export async function runInference() {
  if (store.get('inferenceRunning')) return;
  store.set('inferenceRunning', true);

  const btn = document.getElementById('btn-inference');
  if (btn) { btn.disabled = true; btn.textContent = '실행 중…'; }

  try {
    await safeFetch('/api/inference/run', { method: 'POST' });
  } catch {
    showToast('⚠️ 추론 API 호출 실패 (mock 시퀀스로 진행)', 'info');
  }

  store.emit('inference:start');
}

export async function runWithThresholds(weights) {
  store.set('thresholdRunning', true);
  try {
    const result = await safeFetch('/api/inference/run-with-thresholds', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ weights }),
    });
    // 사용자 설정 localStorage 저장
    localStorage.setItem('threshold_weights', JSON.stringify(weights));
    store.set('thresholdWeights', weights);
    store.set('thresholdResult', result);
  } catch (e) {
    showToast('⚠️ 시뮬레이션 실패: ' + (e.message ?? ''), 'info');
  } finally {
    store.set('thresholdRunning', false);
  }
}
