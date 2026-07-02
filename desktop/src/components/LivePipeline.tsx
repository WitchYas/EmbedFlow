import React, { useRef, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Terminal, X, Zap, Shield, Cpu, Activity } from 'lucide-react';

interface LivePipelineProps {
  runId: string;
  logs: any[];
  onClose: () => void;
}

export const LivePipeline: React.FC<LivePipelineProps> = ({ runId, logs, onClose }) => {
  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const stages = [
    { id: 'security', label: 'Security Scan', icon: Shield },
    { id: 'testing', label: 'Unit Testing', icon: Activity },
    { id: 'firmware', label: 'Build Firmware', icon: Cpu },
  ];

  return (
    <motion.div 
      initial={{ x: 600 }}
      animate={{ x: 0 }}
      exit={{ x: 600 }}
      className="fixed right-0 top-16 bottom-0 w-[500px] bg-[#161b22] border-l border-[#30363d] z-50 flex flex-col shadow-2xl"
    >
      <div className="flex flex-col h-full bg-[#0d1117]/50 backdrop-blur-md">
        <div className="p-6 border-b border-[#30363d] flex items-center justify-between bg-[#161b22]">
          <div>
            <h2 className="text-lg font-bold flex items-center gap-2">
              <Zap className="w-4 h-4 text-yellow-500 fill-yellow-500" /> 
              Live Stream: <span className="font-mono text-blue-500 text-sm">{runId.slice(0, 8)}</span>
            </h2>
          </div>
          <button onClick={onClose} className="p-1.5 hover:bg-white/5 rounded-lg transition-colors">
            <X size={20} />
          </button>
        </div>

        <div className="flex-1 flex flex-col min-h-0">
          {/* Progress Visual - Compact */}
          <div className="p-4 grid grid-cols-3 gap-2 bg-[#161b22]/50">
            {stages.map((stage) => {
              const isDone = logs.some(l => l.agent?.toLowerCase().includes(stage.id));
              return (
                <div 
                  key={stage.id} 
                  className={`p-2 rounded-lg border flex flex-col items-center gap-1 transition-all ${
                    isDone ? 'bg-green-500/10 border-green-500/30' : 'bg-slate-900 border-slate-800'
                  }`}
                >
                  <stage.icon size={14} className={isDone ? 'text-green-500' : 'text-slate-600'} />
                  <span className={`text-[9px] font-bold uppercase ${isDone ? 'text-green-500/80' : 'text-slate-500'}`}>
                    {stage.label.split(' ')[0]}
                  </span>
                </div>
              );
            })}
          </div>

          {/* Terminal - Integrated */}
          <div className="flex-1 flex flex-col min-h-0 bg-black/40">
            <div className="px-4 py-2 bg-black/60 border-y border-[#30363d] flex items-center gap-2">
              <Terminal size={12} className="text-gray-600" />
              <span className="text-[9px] font-mono text-gray-600 uppercase tracking-widest">System Logs</span>
            </div>
            <div className="flex-1 overflow-y-auto p-4 font-mono text-[11px] space-y-1.5 custom-scrollbar">
              {logs.length === 0 ? (
                <div className="text-gray-700 animate-pulse italic">Connecting to agent mesh...</div>
              ) : (
                logs.map((log, i) => (
                  <div key={i} className="flex gap-3 leading-relaxed">
                    <span className="text-gray-700 shrink-0">{new Date(log.timestamp).toLocaleTimeString([], { hour12: false, minute: '2-digit', second: '2-digit' })}</span>
                    <span className={`shrink-0 ${log.level === 'error' ? 'text-red-500' : 'text-blue-500/80'}`}>[{log.agent?.slice(0,4).toUpperCase()}]</span>
                    <span className={log.level === 'error' ? 'text-red-400' : 'text-gray-400'}>{log.message}</span>
                  </div>
                ))
              )}
              <div ref={logEndRef} />
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
};
