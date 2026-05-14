import { safeFetch } from './client.js';
import { store } from '../state/store.js';

// 프롬프트 구조 변경 시 버전 올리면 당일 캐시 자동 무효화
const CACHE_VERSION  = 'v2';
const CACHE_KEY      = `briefing_data_${CACHE_VERSION}`;
const CACHE_DATE_KEY = `briefing_date_${CACHE_VERSION}`;

export async function loadBriefing(forceRefresh = false) {
  const today      = new Date().toISOString().split('T')[0];
  const cachedDate = localStorage.getItem(CACHE_DATE_KEY);
  const cachedData = localStorage.getItem(CACHE_KEY);

  if (!forceRefresh && cachedDate === today && cachedData) {
    store.set('briefing', JSON.parse(cachedData));
    return;
  }

  store.set('briefingLoading', true);

  try {
    // LM Studio reasoning 포함 시 90초+ 소요 → 150초 타임아웃
    const data = await safeFetch('/api/briefing/daily?top_n=5', {}, 150000);
    localStorage.setItem(CACHE_KEY,      JSON.stringify(data));
    localStorage.setItem(CACHE_DATE_KEY, today);
    store.set('briefing', data);
  } catch {
    store.set('briefing', { error: true });
  } finally {
    store.set('briefingLoading', false);
  }
}
