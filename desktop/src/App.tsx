import React, { useState, useEffect, useCallback } from "react";
import { 
  Activity, Shield, Cpu, Terminal, MessageSquare, Settings, 
  LayoutDashboard, Play, CheckCircle2, XCircle, AlertTriangle, 
  ChevronRight, ExternalLink, Plus, Send, Sparkles, Zap, 
  Loader2, RefreshCw, Search, Filter, ArrowRight, Workflow, 
  Eye, Settings2, Database, Brain
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { 
  BarChart, Bar, 
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  Cell
} from "recharts";
import { api } from "./api";
import { useWebSocket } from "./hooks/useWebSocket";
import { LivePipeline } from "./components/LivePipeline";
import { AgentWorkflow } from "./components/AgentWorkflow";
import { ThinkingDrawer } from "./components/ThinkingDrawer";
import { SecurityInsights } from "./components/SecurityInsights";

export default function App() {
  const [activeTab, setActiveTab ] = useState("overview");
  const [runs, setRuns] = useState<any[]>([]);
  const [selectedRun, setSelectedRun] = useState<any>(null);
  const [isThinkingOpen, setIsThinkingOpen] = useState(false);
  const [healthStatus, setHealthStatus] = useState<any>({
    api: "up", db: "up", redis: "up", sim: "up", ollama: "up"
  });
  const [isDeploying, setIsDeploying] = useState(false);
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);
  const [chatMessage, setChatMessage] = useState("");
  const [chatHistory, setChatHistory] = useState<any[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const [activeModel, setActiveModel] = useState<"phi3" | "deepseek">("phi3");
  const [isScenarioOpen, setIsScenarioOpen] = useState(false);
  const [selectedScenarioId, setSelectedScenarioId] = useState("s1");

  const scenarios = [
    {
      id: "s1",
      label: "S1 Golden Path",
      description: "Clean image, all tests pass.",
      firmwarePath: "firmware/v1.2.0.bin",
      firmwareImage: "ubuntu:22.04",
    },
    {
      id: "s2",
      label: "S2 CVE Block",
      description: "Critical vulnerabilities detected.",
      firmwarePath: "firmware/cve-block.bin",
      firmwareImage: "nginx:1.14.0",
    },
    {
      id: "s3",
      label: "S3 Reflection Loop",
      description: "Ambiguous risk triggers reflection.",
      firmwarePath: "firmware/reflection.bin",
      firmwareImage: "python:3.9-slim",
    },
    {
      id: "s4",
      label: "S4 Self-Healing",
      description: "Resilience scenario with recovery.",
      firmwarePath: "firmware/self-healing.bin",
      firmwareImage: "node:14-alpine",
    },
  ];

  const { logs } = useWebSocket(currentRunId);

  const refreshData = useCallback(async () => {
    try {
      const data = await api.getRuns();
      setRuns(data || []);
      const health = await api.getHealth();
      setHealthStatus({
        api: health.status === "ok" ? "up" : "down",
        db: (health.database === "ok" || health.database === "connected") ? "up" : "down",
        redis: (health.redis === "ok" || health.redis === "connected") ? "up" : "down",
        sim: "up",
        ollama: "up"
      });
    } catch (e) { console.error(e); }
  }, []);

  useEffect(() => {
    refreshData();
    const interval = setInterval(refreshData, 5000);
    return () => clearInterval(interval);
  }, [refreshData]);

  const handleDeploy = async () => {
    try {
      const scenario = scenarios.find(s => s.id === selectedScenarioId) || scenarios[0];
      setIsDeploying(true);
      const res = await api.triggerPipeline({
        firmware_path: scenario.firmwarePath,
        device_profile: "rpi4",
        firmware_image: scenario.firmwareImage,
      });
      if (res.run_id) {
        setCurrentRunId(res.run_id);
      }
    } catch (e) {
      alert("Deployment failed to initiate.");
      setIsDeploying(false);
    }
  };

  const handleSendMessage = async () => {
    if (!chatMessage.trim() || !selectedRun) return;
    const userMsg = { role: "user", content: chatMessage };
    setChatHistory((prev: any[]) => [...prev, userMsg]);
    setChatMessage("");
    setIsTyping(true);
    try {
      const res = await api.chat(selectedRun.id, chatMessage, activeModel);
      setChatHistory((prev: any[]) => [...prev, { role: "assistant", content: res.response, model: res.model }]);
    } catch (e) { setChatHistory((prev: any[]) => [...prev, { role: "system", content: "Offline" }]); }
    finally { setIsTyping(false); }
  };

  const DecisionBadge = ({ decision }: { decision: string }) => {
    const styles: any = {
      DEPLOY: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20",
      BLOCK: "bg-rose-500/10 text-rose-500 border-rose-500/20",
      REVIEW: "bg-amber-500/10 text-amber-500 border-amber-500/20"
    };
    return (
      <span className={`px-2 py-0.5 rounded-full text-[9px] font-black border uppercase tracking-widest ${styles[decision] || "bg-white/5 text-white/40"}`}>
        {decision || "PENDING"}
      </span>
    );
  };

  return (
    <div className="flex h-screen bg-[#0d1117] text-white overflow-hidden font-sans">
      <aside className="w-20 lg:w-64 bg-[#161b22] border-r border-[#30363d] flex flex-col z-30 transition-all duration-300">
        <div className="p-6 lg:p-8 flex items-center gap-3">
          <div className="w-10 h-10 min-w-[40px] bg-gradient-to-tr from-blue-600 to-indigo-600 rounded-xl flex items-center justify-center font-black shadow-2xl shadow-blue-500/20">⬡</div>
          <div className="hidden lg:block overflow-hidden whitespace-nowrap">
            <span className="font-black text-sm block">OMNIPOTENT</span>
            <span className="text-[9px] text-blue-500 font-bold tracking-[0.3em] uppercase opacity-60">Control Plane</span>
          </div>
        </div>

        <nav className="flex-1 px-3 lg:px-4 space-y-1.5 mt-4">
          {[
            { id: "overview", icon: LayoutDashboard, label: "Dashboard" },
            { id: "pipelines", icon: Workflow, label: "Agent Mesh" },
            { id: "metrics", icon: Activity, label: "Telemetry" },
            { id: "ai", icon: Sparkles, label: "AI Expert" },
          ].map(item => (
            <button
              key={item.id}
              onClick={() => { setActiveTab(item.id); if (item.id !== "pipelines" && item.id !== "ai") setSelectedRun(null); }}
              className={`w-full flex items-center gap-4 px-3 lg:px-4 py-3.5 rounded-2xl text-sm font-semibold transition-all ${
                activeTab === item.id ? "bg-blue-600 text-white shadow-xl shadow-blue-600/20" : "text-gray-400 hover:bg-white/5 hover:text-white"
              }`}
            >
              <item.icon size={20} />
              <span className="hidden lg:block">{item.label}</span>
            </button>
          ))}
        </nav>

        <div className="p-4 lg:p-6 mb-4">
           <button onClick={() => setIsScenarioOpen(true)} className="w-full bg-slate-800 hover:bg-emerald-600 text-white py-3 rounded-xl border border-white/5 flex items-center justify-center transition-all">
             <Plus size={20} />
             <span className="hidden lg:block ml-2 font-bold">New Run</span>
           </button>
        </div>
      </aside>

      <main className="flex-1 flex flex-col min-w-0 bg-[#0d1117] relative">
        <header className="h-20 border-b border-[#30363d] flex items-center justify-between px-8 bg-[#0d1117]/80 backdrop-blur-xl z-20 sticky top-0">
          <div className="flex items-center gap-6">
            <h1 className="text-sm font-black text-gray-400 uppercase tracking-[0.4em]">{activeTab}</h1>
            <div className="hidden md:flex gap-1 p-1 bg-white/5 rounded-xl border border-white/5">
               {Object.entries(healthStatus).map(([name, status]) => (
                 <div key={name} className="flex items-center gap-2 px-3 py-1 border-r last:border-0 border-white/10 group">
                    <div className={`w-1.5 h-1.5 rounded-full ${status === "up" ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]" : "bg-rose-500"}`} />
                    <span className="text-[10px] font-black uppercase text-gray-500 group-hover:text-gray-300 transition-colors">{name}</span>
                 </div>
               ))}
            </div>
          </div>
          <div className="flex gap-4">
             <button onClick={refreshData} className="p-2.5 bg-white/5 rounded-xl hover:bg-white/10 transition-colors text-gray-400"><RefreshCw size={18} /></button>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto p-8 custom-scrollbar">
          <AnimatePresence mode="wait">
            {activeTab === "overview" && (
              <motion.div key="ov" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="space-y-10 max-w-7xl mx-auto">
                <div className="grid grid-cols-12 gap-8">
                  <div className="col-span-12 lg:col-span-8 bg-gradient-to-br from-[#1c2128] to-[#0d1117] p-12 rounded-[40px] border border-[#30363d] relative overflow-hidden shadow-2xl group">
                     <div className="absolute top-0 right-0 w-full h-full bg-[radial-gradient(circle_at_top_right,rgba(59,130,246,0.08),transparent_50%)]" />
                     <div className="relative z-10">
                        <span className="text-blue-500 font-black text-[10px] tracking-[0.5em] uppercase mb-4 block">System Consensus</span>
                        {runs[0] ? (
                          <>
                            <div className={`text-9xl font-black font-mono tracking-tighter flex items-center gap-10 ${runs[0].decision === "BLOCK" ? "text-rose-500" : "text-emerald-500"}`}>
                              {runs[0].decision} 
                              {runs[0].decision === "BLOCK" ? <XCircle size={100} strokeWidth={3} /> : <CheckCircle2 size={100} strokeWidth={3} />}
                            </div>
                            <div className="mt-12 grid grid-cols-2 gap-20 border-t border-white/5 pt-10">
                               <div>
                                  <span className="text-[10px] font-black text-gray-500 uppercase tracking-widest block mb-1">Model Confidence</span>
                                  <div className="text-5xl font-mono font-bold">{(runs[0].confidence * 100).toFixed(2)}%</div>
                               </div>
                               <div>
                                  <span className="text-[10px] font-black text-gray-500 uppercase tracking-widest block mb-2">Justification Trace</span>
                                  <p className="text-gray-400 text-sm italic font-medium leading-relaxed">"{runs[0].decision_details?.find((d: any) => d.agent_name === "orchestrator")?.output?.justification || "No trace recorded."}"</p>
                               </div>
                            </div>
                          </>
                        ) : <div className="text-4xl font-black text-gray-800 animate-pulse py-20 uppercase tracking-widest">Hydrating Mesh State...</div>}
                     </div>
                  </div>
                  <div className="col-span-12 lg:col-span-4 bg-[#161b22] rounded-[40px] border border-[#30363d] p-10 flex flex-col justify-center">
                    <div className="space-y-8">
                      {[{ l: "Total Runs", v: runs.length, c: "text-blue-500" }, { l: "Block Rate", v: `${Math.round((runs.filter((r: any) => r.decision === "BLOCK").length / (runs.length || 1)) * 100)}%`, c: "text-rose-500" }, { l: "Active Agents", v: "3", c: "text-purple-500" }].map(s => (
                        <div key={s.l}>
                          <span className="text-[10px] font-black text-gray-500 uppercase tracking-widest block mb-1">{s.l}</span>
                          <div className={`text-4xl font-black font-mono tracking-tighter ${s.c}`}>{s.v}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
                   {[
                    { l: "Network Latency", v: "42ms", i: Zap, color: "text-amber-400" },
                    { l: "DB Threads", v: "Active", i: Database, color: "text-emerald-400" },
                    { l: "CVE Database", v: "Sync", i: Shield, color: "text-blue-400" },
                    { l: "AI Heatmap", v: "Optimal", i: Brain, color: "text-purple-400" }
                   ].map(card => (
                     <div key={card.l} className="bg-[#161b22] p-8 rounded-3xl border border-[#30363d] transition-all">
                        <card.i size={24} className={`${card.color} mb-6`} />
                        <span className="text-[10px] font-black text-gray-500 uppercase tracking-widest block mb-1">{card.l}</span>
                        <div className="text-2xl font-black tracking-tighter">{card.v}</div>
                     </div>
                   ))}
                </div>
              </motion.div>
            )}

            {activeTab === "pipelines" && (
              <div className="h-full flex flex-col space-y-8 min-h-0">
                <div className="bg-[#161b22] border border-[#30363d] rounded-[32px] overflow-hidden shadow-2xl">
                  <div className="flex-1 overflow-y-auto max-h-[400px] custom-scrollbar">
                    <table className="w-full text-left border-collapse">
                      <thead className="bg-[#1c2128] text-[9px] uppercase text-gray-500 border-b border-[#30363d] sticky top-0 z-10 font-black tracking-widest">
                        <tr>
                          <th className="px-8 py-6">Identity</th>
                          <th className="px-8 py-6">Environment</th>
                          <th className="px-8 py-6">Operation Status</th>
                          <th className="px-8 py-6">Model Truth</th>
                          <th className="px-8 py-6 text-right">Trace</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#30363d]">
                        {runs.map((run: any) => (
                          <tr key={run.id} onClick={() => setSelectedRun(run)} className={`hover:bg-blue-500/5 cursor-pointer transition-all duration-300 group ${selectedRun?.id === run.id ? "bg-blue-500/10" : ""}`}>
                            <td className="px-8 py-6">
                              <div className="font-mono text-sm text-blue-400">run-{run.id.slice(0,8)}</div>
                              <div className="text-[10px] text-gray-500 font-mono mt-1 opacity-60 italic">{run.firmware_hash?.slice(0,16)}</div>
                            </td>
                            <td className="px-8 py-6">
                              <div className="flex items-center gap-2">
                                <Cpu size={14} className="text-gray-600" />
                                <span className="text-[10px] font-black text-gray-400">{run.profile?.toUpperCase()}</span>
                              </div>
                            </td>
                            <td className="px-8 py-6">
                               <div className="flex items-center gap-4">
                                  <div className="min-w-[80px]">
                                    {run.status === "running" ? (
                                      <div className="flex items-center gap-2 text-blue-400 font-black text-[10px] animate-pulse">
                                        <Loader2 size={12} className="animate-spin" /> RUNNING
                                      </div>
                                    ) : <span className="text-[10px] font-black text-slate-500 uppercase">{run.status}</span>}
                                  </div>
                                  {run.status === "running" && (
                                    <button onClick={(e) => { e.stopPropagation(); setCurrentRunId(run.id); setIsDeploying(true); }} className="px-3 py-1.5 bg-blue-600 text-[10px] font-black rounded-lg shadow-lg shadow-blue-500/10 hover:bg-blue-500 flex items-center gap-2">
                                      <Terminal size={12} /> LOGS
                                    </button>
                                  )}
                               </div>
                            </td>
                            <td className="px-8 py-6">
                               <div className="flex items-center gap-4">
                                  <div className="w-20"><DecisionBadge decision={run.decision} /></div>
                                  <span className="text-[10px] font-mono font-bold text-gray-500">{(run.confidence * 100).toFixed(0)}%</span>
                               </div>
                            </td>
                            <td className="px-8 py-6 text-right">
                               <ChevronRight size={20} className="text-gray-700 active:text-blue-500 transition-all inline" />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {selectedRun && (
                  <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} className="flex flex-col gap-8">
                     <div className="bg-[#161b22] border-2 border-blue-500/20 rounded-[40px] p-10 shadow-2xl relative">
                        <button onClick={() => setSelectedRun(null)} className="absolute top-8 right-8 p-2.5 hover:bg-white/10 rounded-full transition-colors"><XCircle size={24} className="text-gray-500 hover:text-white" /></button>
                        
                        <div className="flex flex-col lg:flex-row gap-12">
                           <div className="flex-1 space-y-10">
                              <div className="flex items-center gap-5">
                                 <div className="p-4 bg-blue-600/10 rounded-3xl border border-blue-500/20 shadow-inner"><Cpu size={32} className="text-blue-400" /></div>
                                 <div className="space-y-1">
                                    <h3 className="text-3xl font-black tracking-tight uppercase">Technical Trace</h3>
                                    <p className="text-[10px] font-black text-blue-500 tracking-[0.4em] uppercase opacity-60">Report ID: {selectedRun.id}</p>
                                 </div>
                              </div>

                              <div className="bg-black/20 rounded-[32px] p-8 border border-white/5">
                                 <h4 className="text-[10px] font-black text-gray-500 uppercase tracking-widest mb-6">Autonomous Reasoning Flow</h4>
                                 <AgentWorkflow status={selectedRun.status} activeAgents={["security", "testing", "orchestrator"]} />
                              </div>

                              <div className="grid grid-cols-2 gap-6">
                                 <div className="bg-black/20 p-8 rounded-[32px] border border-white/5">
                                    <h4 className="text-[10px] font-black text-blue-500 uppercase tracking-widest mb-4">Core Justification</h4>
                                    <p className="text-sm text-slate-300 font-medium italic leading-relaxed">"{selectedRun.decision_details?.find((d: any) => d.agent_name === "orchestrator")?.output?.justification || "No log data."}"</p>
                                 </div>
                                 <div className="bg-black/20 p-8 rounded-[32px] border border-white/5">
                                    <h4 className="text-[10px] font-black text-amber-500 uppercase tracking-widest mb-4">AI Reflection Logic</h4>
                                    {selectedRun.decision_details?.find((d: any) => d.agent_name === "orchestrator")?.output?.reflection_note ? (
                                      <p className="text-xs text-amber-400 font-mono bg-amber-500/5 p-4 rounded-2xl border border-amber-500/10">{selectedRun.decision_details.find((d: any) => d.agent_name === "orchestrator").output.reflection_note}</p>
                                    ) : <p className="text-xs text-gray-600 italic">Consensus reached. No reflection required.</p>}
                                 </div>
                              </div>
                           </div>

                           <div className="w-full lg:w-[400px] space-y-8 min-w-0">
                               <div className="bg-black/20 p-8 rounded-[32px] border border-white/5 h-full">
                                  <h4 className="text-[10px] font-black text-rose-500 uppercase tracking-widest mb-8">Vulnerability Metrics</h4>
                                  <SecurityInsights 
                                    cves={selectedRun.decision_details?.find((d: any) => d.agent_name === "security_agent")?.output || { critical: 0, high: 0, medium: 0, low: 0 }} 
                                    sbom={Array.isArray(selectedRun.sbom_entries) ? selectedRun.sbom_entries : []} 
                                    layout="stack"
                                  />
                               </div>
                           </div>
                        </div>
                     </div>
                  </motion.div>
                )}
              </div>
            )}

            {activeTab === "metrics" && (
              <motion.div key="mt" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="grid grid-cols-1 lg:grid-cols-2 gap-10 max-w-7xl mx-auto">
                 <div className="bg-[#161b22] border border-[#30363d] rounded-[40px] p-10">
                    <h3 className="text-[10px] font-black text-gray-400 uppercase tracking-[0.3em] mb-12">Historical Confidence Gradient</h3>
                    <div className="h-80 box-content">
                       <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={runs.slice().reverse()}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#30363d" vertical={false} />
                            <XAxis dataKey="id" tickFormatter={(v: string) => v.slice(0,4)} stroke="#6e7681" fontSize={10} axisLine={false} tickLine={false} />
                            <YAxis axisLine={false} tickLine={false} stroke="#6e7681" fontSize={10} />
                            <Tooltip contentStyle={{ backgroundColor: "#0d1117", border: "1px solid #30363d", borderRadius: "16px" }} />
                            <Bar dataKey="confidence" radius={[10, 10, 0, 0]} barSize={24}>
                              {runs.slice().reverse().map((e: any, index: number) => <Cell key={index} fill={e.decision === "BLOCK" ? "#f43f5e" : "#10b981"} fillOpacity={0.8} />)}
                            </Bar>
                          </BarChart>
                       </ResponsiveContainer>
                    </div>
                 </div>
                 <div className="bg-[#161b22] border border-[#30363d] rounded-[40px] p-10">
                    <h3 className="text-[10px] font-black text-gray-400 uppercase tracking-[0.3em] mb-10">Backend Mesh Protocol</h3>
                    <div className="space-y-4">
                       {Object.entries(healthStatus).map(([name, status]) => (
                         <div key={name} className="flex items-center justify-between p-6 bg-black/20 rounded-3xl border border-white/5 transition-all hover:bg-black/40">
                            <div className="flex items-center gap-5">
                               <div className={`p-3 rounded-2xl bg-white/5 ${status === "up" ? "text-emerald-400" : "text-rose-400"}`}>{name === "ollama" ? <Sparkles size={20} /> : <Database size={20} />}</div>
                               <div><span className="text-xs font-black uppercase tracking-widest block">{name}</span><span className="text-[9px] font-mono text-gray-500">UPTIME_OK</span></div>
                            </div>
                            <div className={`px-4 py-1.5 rounded-full text-[9px] font-black border ${status === "up" ? "bg-emerald-500/10 text-emerald-500 border-emerald-500/20" : "bg-rose-500/10 text-rose-500 border-rose-500/20"}`}>{status === "up" ? "HEALTHY" : "FAILED"}</div>
                         </div>
                       ))}
                    </div>
                 </div>
              </motion.div>
            )}

            {activeTab === "ai" && (
              <motion.div key="ai" initial={{ opacity: 0, x: 40 }} animate={{ opacity: 1, x: 0 }} className="h-full max-w-5xl mx-auto flex flex-col pb-8">
                 <div className="flex-1 flex flex-col bg-[#161b22] border-2 border-blue-500/20 rounded-[40px] overflow-hidden shadow-2xl relative">
                    <div className="absolute top-0 left-0 w-full h-1.5 bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600" />
                    <div className="p-8 border-b border-[#30363d] flex items-center justify-between bg-white/[0.02]">
                       <div className="flex items-center gap-5">
                          <div className="p-4 bg-blue-600/10 rounded-[20px] shadow-inner"><Sparkles size={28} className="text-blue-400" /></div>
                          <div><span className="font-black text-2xl tracking-tighter">AI AGENT ADVISOR</span><div className="flex items-center gap-2 mt-1"><div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" /><span className="text-[10px] font-black text-gray-500 uppercase tracking-widest">Active Reasoning Session</span></div></div>
                       </div>
                    </div>
                    <div className="flex-1 overflow-y-auto p-12 space-y-8 custom-scrollbar bg-black/5">
                       {chatHistory.length === 0 && <div className="h-full flex flex-col items-center justify-center opacity-10 grayscale scale-150"><Brain size={120} /></div>}
                       {chatHistory.map((m: any, i: number) => (
                         <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                            <div className={`max-w-[75%] rounded-[32px] px-8 py-5 text-sm leading-relaxed shadow-lg ${m.role === "user" ? "bg-blue-600 text-white font-semibold" : "bg-[#1c2128] border border-[#30363d] text-slate-300"}`}>{m.content}</div>
                         </div>
                       ))}
                       {isTyping && <div className="text-[10px] font-black text-blue-500 animate-pulse uppercase tracking-[0.4em] pl-4">Orchestrator is thinking...</div>}
                    </div>
                    <div className="p-8 bg-[#161b22] border-t border-[#30363d]">
                       <div className="flex gap-4">
                          <input value={chatMessage} onChange={e => setChatMessage(e.target.value)} onKeyDown={e => e.key === "Enter" && handleSendMessage()} placeholder={selectedRun ? `Query session run-${selectedRun.id.slice(0,8)}...` : "Select a run in Agent Mesh first"} disabled={!selectedRun} className="flex-1 bg-black/40 border-2 border-white/5 rounded-3xl px-8 py-5 text-sm focus:outline-none focus:border-blue-500 transition-all font-medium" />
                          <button onClick={handleSendMessage} className="px-10 bg-blue-600 rounded-3xl hover:bg-blue-700 transition-all active:scale-95"><Send size={24} /></button>
                       </div>
                    </div>
                 </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </main>

      {isScenarioOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-6">
          <div className="w-full max-w-3xl bg-[#161b22] border border-[#30363d] rounded-[32px] shadow-2xl overflow-hidden">
            <div className="flex items-center justify-between p-6 border-b border-[#30363d]">
              <div>
                <h2 className="text-lg font-black uppercase tracking-widest">Select Run Scenario</h2>
                <p className="text-[11px] text-gray-500 uppercase tracking-widest mt-1">Pick a demo path</p>
              </div>
              <button onClick={() => setIsScenarioOpen(false)} className="p-2 rounded-xl hover:bg-white/10 transition-colors">
                <XCircle size={20} className="text-gray-400" />
              </button>
            </div>

            <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-4">
              {scenarios.map((scenario) => (
                <button
                  key={scenario.id}
                  onClick={() => setSelectedScenarioId(scenario.id)}
                  className={`text-left p-5 rounded-2xl border transition-all ${
                    selectedScenarioId === scenario.id
                      ? "bg-blue-600/10 border-blue-500/30 shadow-xl shadow-blue-500/10"
                      : "bg-black/20 border-white/5 hover:border-white/20"
                  }`}
                >
                  <div className="text-xs font-black uppercase tracking-widest text-blue-400">{scenario.label}</div>
                  <div className="text-sm text-slate-300 mt-2">{scenario.description}</div>
                  <div className="mt-4 text-[10px] font-mono text-slate-500">
                    Image: {scenario.firmwareImage}
                  </div>
                </button>
              ))}
            </div>

            <div className="p-6 flex items-center justify-end gap-3 border-t border-[#30363d] bg-black/20">
              <button onClick={() => setIsScenarioOpen(false)} className="px-5 py-2.5 text-xs font-black uppercase tracking-widest text-gray-400 hover:text-white">
                Cancel
              </button>
              <button
                onClick={() => { setIsScenarioOpen(false); handleDeploy(); }}
                className="px-6 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-xs font-black uppercase tracking-widest rounded-xl shadow-lg shadow-emerald-600/20"
              >
                Launch Run
              </button>
            </div>
          </div>
        </div>
      )}

      {isDeploying && currentRunId && (
        <LivePipeline runId={currentRunId} logs={logs} onClose={() => { setIsDeploying(false); setCurrentRunId(null); refreshData(); }} />
      )}

      <style>{`
        .custom-scrollbar::-webkit-scrollbar { width: 4px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #30363d; border-radius: 10px; }
      `}</style>
    </div>
  );
}
