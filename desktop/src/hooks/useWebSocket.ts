import { useState, useEffect, useRef } from 'react';
import { LogEntry } from '../types';

export function useWebSocket(runId: string | null) {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!runId) {
      setLogs([]);
      return;
    }

    const socket = new WebSocket(`ws://172.18.205.88:8000/ws/pipeline/${runId}`);
    socketRef.current = socket;

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'log' || data.type === 'final') {
        setLogs((prev) => [...prev, data]);
      }
    };

    socket.onclose = () => {
      console.log('WS Connection closed');
    };

    return () => {
      socket.close();
    };
  }, [runId]);

  return { logs };
}
