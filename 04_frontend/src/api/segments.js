import { safeFetch } from './client.js';
import { store } from '../state/store.js';
import { toast } from '../utils/toast.js';

export async function loadSegments() {
  store.set('segmentsLoading', true);
  try {
    const list = await safeFetch('/api/segments');
    // loading → false 먼저: render()가 실행될 때 loading 상태가 false여야 실제 목록이 표시됨
    store.set('segmentsLoading', false);
    store.set('segments', list);
  } catch {
    store.set('segmentsLoading', false);
    store.set('segments', []);
  }
}

export async function loadDetail(segId) {
  store.set('selectedId', segId);
  store.set('inferenceTrace', null);
  try {
    const [detail, lineage, trace] = await Promise.all([
      safeFetch(`/api/segments/${segId}`),
      safeFetch(`/api/segments/${segId}/lineage`),
      safeFetch(`/api/segments/${segId}/inference-trace`),
    ]);
    store.set('detail', detail);
    store.set('lineage', lineage);
    store.set('inferenceTrace', trace);
  } catch {
    toast('상세 정보 로드 실패');
  }
}
