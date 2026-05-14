export const API_BASE = 'http://localhost:8001';

export const STATE_COLOR = {
  ImmediatePreWatering: '#ef4444',
  PriorityPreWatering:  '#f97316',
  ReviewPreWatering:    '#eab308',
  EnhancedMonitoring:   '#3b82f6',
  GeneralManagement:    '#22c55e',
  NotActionable:        '#6b7280',
};

export const STATE_KR = {
  ImmediatePreWatering: '즉시 예비주수',
  PriorityPreWatering:  '우선 예비주수',
  ReviewPreWatering:    '검토 예비주수',
  EnhancedMonitoring:   '강화 모니터링',
  GeneralManagement:    '일반 관리',
  NotActionable:        '조치 불가',
};

export const FEATURE_LABEL = {
  FireRiskLevel:       '화재위험수준',
  ResidentialExposure: '주거노출도',
  WindTowardAsset:     '자산방향풍속',
};

export const SIGNAL_LABEL = {
  S_official: '공식지수(S_official)',
  S_exposure: '노출지수(S_exposure)',
};

export const OVERRIDE_LABEL = {
  GradeSevere: '등급상향(GradeSevere)',
  HazardGate:  '위험차단(HazardGate)',
  none:        '없음',
};

export function spColor(sp) {
  if (sp >= 0.80) return '#ef4444';
  if (sp >= 0.60) return '#f97316';
  if (sp >= 0.40) return '#eab308';
  if (sp >= 0.20) return '#3b82f6';
  return '#22c55e';
}
