'use client';

import styles from './PipelineVisualizer.module.css';

interface Stage {
  name: string;
  icon: string;
  status: 'idle' | 'running' | 'done' | 'error';
  items?: number;
  duration_ms?: number;
}

interface PipelineVisualizerProps {
  stages: Stage[];
}

const DEFAULT_STAGES: Stage[] = [
  { name: 'Watcher', icon: '👁', status: 'idle' },
  { name: 'Analyzer', icon: '📊', status: 'idle' },
  { name: 'Context', icon: '🌐', status: 'idle' },
  { name: 'Bayesian', icon: '🧠', status: 'idle' },
  { name: 'Risk', icon: '🛡', status: 'idle' },
  { name: 'Execute', icon: '⚡', status: 'idle' },
  { name: 'BigBro', icon: '🔮', status: 'idle' },
];

export default function PipelineVisualizer({ stages }: PipelineVisualizerProps) {
  const displayStages = stages.length > 0 ? stages : DEFAULT_STAGES;

  return (
    <div className={styles.pipeline}>
      {displayStages.map((stage, i) => (
        <div key={stage.name} className={styles.stageGroup}>
          <div className={`${styles.stage} ${styles[stage.status]}`}>
            <span className={styles.icon}>{stage.icon}</span>
            <span className={styles.name}>{stage.name}</span>
            {stage.items !== undefined && (
              <span className={styles.count}>{stage.items}</span>
            )}
            {stage.duration_ms !== undefined && (
              <span className={styles.duration}>{stage.duration_ms}ms</span>
            )}
          </div>
          {i < displayStages.length - 1 && (
            <div className={styles.connector}>
              <div className={`pipeline-flow ${stage.status === 'done' ? styles.flowActive : ''}`} />
              <span className={styles.arrow}>→</span>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
