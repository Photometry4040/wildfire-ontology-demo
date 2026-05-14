import './styles/base.css';
import './styles/components.css';

import { checkHealth } from './api/client.js';
import { loadSegments } from './api/segments.js';
import { loadBriefing } from './api/briefing.js';
import { runInference } from './api/inference.js';

import { mount as mountPipeline      } from './components/pipeline-panel.js';
import { mount as mountSegmentList   } from './components/segment-list.js';
import { mount as mountSegmentDetail } from './components/segment-detail.js';
import { mount as mountLineageTable  } from './components/lineage-table.js';
import { mount as mountBriefingPanel } from './components/briefing-panel.js';
import { mount as mountLayerStack    } from './components/layer-stack.js';
import { mount as mountRelationGraph } from './components/relation-graph.js';
import { mount as mountDolMeta       } from './components/dol-meta.js';
import { mount as mountGokseongBanner   } from './components/gokseong-banner.js';
import { mount as mountFunctionInference} from './components/function-inference.js';
import { mount as mountStateTimeline    } from './components/state-timeline.js';
import { mount as mountThresholdPanel  } from './components/threshold-panel.js';
import { mount as mountModeSwitch      } from './components/mode-switch.js';
import { mount as mountDolDetail       } from './components/dol-detail.js';

// 헤더 버튼 이벤트 바인딩 (inline onclick 제거됨)
document.getElementById('btn-inference')
  ?.addEventListener('click', runInference);

document.getElementById('briefing-refresh')
  ?.addEventListener('click', () => loadBriefing(true));

// 컴포넌트 마운트
mountPipeline();
mountSegmentList();
mountSegmentDetail();
mountLineageTable();
mountBriefingPanel();
mountLayerStack();
mountRelationGraph();
mountDolMeta();
mountGokseongBanner();
mountFunctionInference();
mountStateTimeline();
mountThresholdPanel();
mountModeSwitch();
mountDolDetail();

// 초기 데이터 로드
(async () => {
  await checkHealth();
  await loadSegments();
  loadBriefing(false);
})();
