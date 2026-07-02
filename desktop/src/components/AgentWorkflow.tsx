import React from 'react';
import { motion } from 'framer-motion';
import { Shield, Cpu, Brain, CheckCircle2, Circle, Loader2, Workflow } from 'lucide-react';

interface AgentWorkflowProps {
  status: 'running' | 'completed' | 'failed' | 'idle';
  activeAgents: string[]; // ['security', 'testing', 'orchestrator']
}

export const AgentWorkflow: React.FC<AgentWorkflowProps> = ({ status, activeAgents }) => {
  const steps = [
    { id: 'security', label: 'Security Agent', icon: Shield, color: 'text-blue-400' },
    { id: 'testing', label: 'Testing Agent', icon: Cpu, color: 'text-purple-400' },
    { id: 'orchestrator', label: 'AI Orchestrator', icon: Brain, color: 'text-amber-400' },
  ];

  return (
    <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6 mb-6">
      <div className="flex items-center gap-2 mb-6">
        <Workflow className="w-5 h-5 text-indigo-400" />
        <h3 className="font-semibold text-slate-200">Stateful Agent Workflow (LangGraph)</h3>
      </div>

      <div className="relative flex justify-between items-start max-w-4xl mx-auto">
        {/* Connection Lines */}
        <div className="absolute top-6 left-0 w-full h-0.5 bg-slate-800 -z-0" />
        
        {steps.map((step, idx) => {
          const isActive = activeAgents.includes(step.id);
          const isPending = status === 'running' && !isActive && idx === 2; // Orchestrator usually runs last
          const isDone = status === 'completed';
          
          return (
            <div key={step.id} className="relative z-10 flex flex-col items-center group w-32">
              <motion.div 
                animate={isActive ? { scale: [1, 1.1, 1], shadow: "0 0 20px rgba(96, 165, 250, 0.5)" } : {}}
                transition={{ repeat: Infinity, duration: 2 }}
                className={`w-12 h-12 rounded-full flex items-center justify-center border-2 transition-colors duration-500
                  ${isActive ? 'bg-slate-800 border-indigo-500 shadow-lg shadow-indigo-500/20' : 
                    isDone ? 'bg-indigo-900/20 border-indigo-500' : 'bg-slate-900 border-slate-800'}`}
              >
                {isActive ? (
                  <Loader2 className={`w-6 h-6 ${step.color} animate-spin`} />
                ) : isDone ? (
                  <CheckCircle2 className="w-6 h-6 text-indigo-400" />
                ) : (
                  <step.icon className={`w-6 h-6 ${isActive ? step.color : 'text-slate-600'}`} />
                )}
              </motion.div>
              
              <div className="mt-3 text-center">
                <p className={`text-xs font-medium uppercase tracking-wider transition-colors duration-500
                  ${isActive ? 'text-indigo-400' : isDone ? 'text-indigo-300' : 'text-slate-500'}`}>
                  {step.label}
                </p>
                {isActive && (
                  <motion.p 
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="text-[10px] text-indigo-400/70 mt-1 font-mono"
                  >
                    Processing...
                  </motion.p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
