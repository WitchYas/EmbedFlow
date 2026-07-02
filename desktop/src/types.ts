export interface LogEntry {
  type: 'log' | 'final' | 'ping';
  run_id?: string;
  agent?: string;
  message?: string;
  level?: 'info' | 'warning' | 'error';
  timestamp?: string;
  decision?: string;
  confidence?: float;
}

export interface PipelineRun {
  id: string;
  firmware_hash: string;
  version?: string;
  status: 'running' | 'completed' | 'failed';
  decision: 'DEPLOY' | 'BLOCK' | 'REVIEW';
  confidence: number;
  triggered: string;
  completed?: string;
  duration: number;
}
