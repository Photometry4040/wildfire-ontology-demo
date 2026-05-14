const DEFAULT_WEIGHTS = {
  S_official: 0.20, S_exposure: 0.25, S_spread: 0.20, S_action: 0.20, S_time: 0.15,
};

const _state = {
  health: null,
  segments: [],
  segmentsLoading: true,
  selectedId: null,
  detail: null,
  lineage: [],
  inferenceTrace: null,
  briefing: null,
  briefingLoading: false,
  pipelineStatus: 'IDLE',
  inferenceRunning: false,
  thresholdWeights: JSON.parse(localStorage.getItem('threshold_weights') || 'null') || { ...DEFAULT_WEIGHTS },
  thresholdResult: null,
  thresholdRunning: false,
  viewMode: localStorage.getItem('view_mode') || 'default',
  activeTab: localStorage.getItem('active_tab') || 'segments',
};

export { DEFAULT_WEIGHTS };

const _listeners = {};

export const store = {
  get(key) {
    return _state[key];
  },

  set(key, val) {
    _state[key] = val;
    (_listeners[key] || []).forEach(fn => fn(val));
  },

  subscribe(key, fn) {
    if (!_listeners[key]) _listeners[key] = [];
    _listeners[key].push(fn);
    return () => {
      _listeners[key] = _listeners[key].filter(f => f !== fn);
    };
  },

  emit(event) {
    (_listeners[event] || []).forEach(fn => fn());
  },

  on(event, fn) {
    if (!_listeners[event]) _listeners[event] = [];
    _listeners[event].push(fn);
  },
};
