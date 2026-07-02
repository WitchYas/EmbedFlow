const API_BASE = 'http://172.18.205.88:8000';

export const api = {
  getRuns: () => fetch(`${API_BASE}/pipeline/runs`).then(r => r.json()),
  getRun: (id: string) => fetch(`${API_BASE}/pipeline/runs/${id}`).then(r => r.json()),
  triggerPipeline: (data: any) => fetch(`${API_BASE}/pipeline/trigger`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  }).then(r => r.json()),
  getHealth: () => fetch(`${API_BASE}/health`).then(r => r.json()),
  
  // Chat
  chat: (runId: string, message: string, modelHint = 'phi3') => fetch(`${API_BASE}/pipeline/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ run_id: runId, message, model_hint: modelHint })
  }).then(r => r.json())
};
