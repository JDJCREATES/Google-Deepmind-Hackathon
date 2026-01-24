import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { 
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  AreaChart, Area, BarChart, Bar
} from 'recharts';
import { config } from '../config';

const API_BASE = `${config.API_URL}/api`;
import { FaDownload, FaFlask, FaSpinner, FaHistory, FaBrain, FaLightbulb, FaChartLine } from 'react-icons/fa';

interface ExperimentSession {
    filename: string;
    created_at: string;
    size_bytes: number;
    is_current: boolean;
}

interface LearningStats {
    total_replays: number;
    optimal_decisions: number;
    suboptimal_decisions: number;
    accuracy_rate: number;
    policy_updates_recommended: number;
}

interface Insight {
    insight: string;
    incident_id: string;
    was_optimal: boolean;
    created_at: string;
}

interface AccuracyPeriod {
    period_start: string;
    period_end: string;
    decisions_in_period: number;
    optimal_decisions: number;
    accuracy: number;
    cumulative_total: number;
}

interface PolicyHistory {
    version: string;
    description: string;
    created_at: string;
    trigger_event: string;
    changes: string[];
}

export default function AnalyticsPage() {
  const [data, setData] = useState<any[]>([]);
  const [sessions, setSessions] = useState<ExperimentSession[]>([]);
  const [selectedSession, setSelectedSession] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  
  // Learning state
  const [activeTab, setActiveTab] = useState<'experiment' | 'learning'>('experiment');
  const [learningStats, setLearningStats] = useState<LearningStats | null>(null);
  const [insights, setInsights] = useState<Insight[]>([]);
  const [policyHistory, setPolicyHistory] = useState<PolicyHistory[]>([]);
  const [accuracyData, setAccuracyData] = useState<AccuracyPeriod[]>([]);
  const [learningLoading, setLearningLoading] = useState(false);

  // 1. Fetch available sessions on mount
  useEffect(() => {
    const fetchSessions = async () => {
        try {
            const res = await fetch(`${API_BASE}/experiment/sessions`);
            const json = await res.json();
            setSessions(json);
            
            // Auto-select current or latest
            if (json.length > 0 && !selectedSession) {
                const current = json.find((s: any) => s.is_current) || json[0];
                setSelectedSession(current.filename);
            } else if (json.length === 0) {
                 setLoading(false);
            }
        } catch (e) {
            console.error("Failed to fetch sessions", e);
            setLoading(false);
        }
    };
    fetchSessions();
  }, []);

  // 2. Fetch stats when selectedSession changes
  useEffect(() => {
    if (!selectedSession) return;

    const fetchStats = async () => {
        setLoading(true);
        try {
            const res = await fetch(`${API_BASE}/experiment/stats?limit=1000&filename=${selectedSession}`);
            const json = await res.json();
            setData(json);
        } catch (e) {
            console.error("Failed to fetch stats", e);
        } finally {
            setLoading(false);
        }
    };

    fetchStats();
    
    // Only poll if it's the CURRENT session
    const isCurrent = sessions.find(s => s.filename === selectedSession)?.is_current;
    if (isCurrent) {
        const interval = setInterval(fetchStats, 5000); // 5s poll
        return () => clearInterval(interval);
    }
  }, [selectedSession, sessions]);

  // 3. Fetch learning data when tab switches to learning
  useEffect(() => {
    if (activeTab !== 'learning') return;
    
    const fetchLearningData = async () => {
        setLearningLoading(true);
        try {
            const [statsRes, insightsRes, historyRes, accuracyRes] = await Promise.all([
                fetch(`${API_BASE}/learning/stats`),
                fetch(`${API_BASE}/learning/insights`),
                fetch(`${API_BASE}/learning/policy-history`),
                fetch(`${API_BASE}/learning/accuracy-over-time`),
            ]);
            
            const stats = await statsRes.json();
            const insightsData = await insightsRes.json();
            const historyData = await historyRes.json();
            const accuracy = await accuracyRes.json();
            
            setLearningStats(stats);
            setInsights(insightsData.insights || []);
            setPolicyHistory(historyData.history || []);
            setAccuracyData(accuracy.periods || []);
        } catch (e) {
            console.error("Failed to fetch learning data", e);
        } finally {
            setLearningLoading(false);
        }
    };
    
    fetchLearningData();
    const interval = setInterval(fetchLearningData, 10000);
    return () => clearInterval(interval);
  }, [activeTab]);


  // Calculate summaries
  const latest = data[data.length - 1] || {};
  const totalRevenue = latest.revenue_cum || 0;
  const totalCost = latest.expenses_cum || 0;
  const roi = totalCost > 0 ? ((totalRevenue - totalCost) / totalCost * 100).toFixed(1) : "0.0";
  
  const currentSessionObj = sessions.find(s => s.filename === selectedSession);

  return (
    <div className="min-h-screen bg-stone-950 text-stone-200 font-sans p-6 overflow-auto">
      {/* HEADER */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between mb-6 border-b border-stone-800 pb-4 gap-4">
        <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-cyan-900/30 rounded flex items-center justify-center text-cyan-400 border border-cyan-800">
                <FaFlask />
            </div>
            <div>
                <h1 className="text-xl font-bold text-stone-100 tracking-tight">DATA & ANALYTICS</h1>
                <p className="text-[10px] text-stone-500 font-mono uppercase tracking-wider flex items-center gap-2">
                   <span>GEMINI-3 INTELLIGENT FACTORY</span>
                   {currentSessionObj?.is_current && <span className="text-emerald-500 animate-pulse">● LIVE</span>}
                </p>
            </div>
        </div>
        
        {/* TAB SWITCHER */}
        <div className="flex items-center gap-2">
            <button 
                onClick={() => setActiveTab('experiment')}
                className={`flex items-center gap-2 px-4 py-2 rounded text-sm font-semibold transition ${
                    activeTab === 'experiment' 
                        ? 'bg-cyan-600 text-white' 
                        : 'bg-stone-800 text-stone-400 hover:bg-stone-700'
                }`}
            >
                <FaChartLine /> Experiment
            </button>
            <button 
                onClick={() => setActiveTab('learning')}
                className={`flex items-center gap-2 px-4 py-2 rounded text-sm font-semibold transition ${
                    activeTab === 'learning' 
                        ? 'bg-purple-600 text-white' 
                        : 'bg-stone-800 text-stone-400 hover:bg-stone-700'
                }`}
            >
                <FaBrain /> System Learning
            </button>
        </div>
      </div>

      {/* ===================== EXPERIMENT TAB ===================== */}
      {activeTab === 'experiment' && (
        <>
          {/* CONTROLS */}
          <div className="flex flex-wrap items-center gap-4 mb-6">
              <div className="flex items-center gap-2 bg-stone-900 border border-stone-800 rounded px-2 py-1">
                  <FaHistory className="text-stone-500 text-xs" />
                  <select 
                      value={selectedSession || ""} 
                      onChange={(e) => setSelectedSession(e.target.value)}
                      className="bg-transparent text-xs text-stone-300 outline-none border-none py-1"
                  >
                      {sessions.map(s => (
                          <option key={s.filename} value={s.filename} className="bg-stone-900">
                              {s.created_at.split('T')[0]} {s.created_at.split('T')[1].split('.')[0]} {s.is_current ? "(Current)" : ""}
                          </option>
                      ))}
                  </select>
              </div>

              <MetricCard label="ROI (Est.)" value={`${roi}%`} color="text-emerald-400" />
              <MetricCard label="Revenue" value={`$${totalRevenue.toLocaleString()}`} color="text-stone-200" />
              <MetricCard label="Agent Cycles" value={data.length.toString()} color="text-stone-400" />
              
              <a 
                  href={`${API_BASE}/experiment/download?filename=${selectedSession}`} 
                  target="_blank"
                  className="flex items-center gap-2 bg-stone-800 hover:bg-stone-700 text-stone-300 px-4 py-2 rounded text-sm font-semibold border border-stone-700 transition"
                  download
              >
                  <FaDownload /> CSV
              </a>
          </div>

          {loading && data.length === 0 ? (
            <div className="h-[400px] w-full flex items-center justify-center text-stone-500 gap-2 border border-stone-800 border-dashed rounded bg-stone-900/20">
                 <FaSpinner className="animate-spin" /> Loading Session Data...
            </div>
          ) : (
            /* CHARTS GRID */
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
                
                {/* CHART 1: FINANCIALS */}
                <div className="bg-stone-900 border border-stone-800 rounded p-4 h-[350px]">
                    <h3 className="text-sm font-bold text-stone-400 mb-4 font-mono uppercase">Financial Performance (Cumulative)</h3>
                    <ResponsiveContainer width="100%" height="90%">
                        <AreaChart data={data}>
                            <defs>
                                <linearGradient id="colorRev" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                                    <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                                </linearGradient>
                                <linearGradient id="colorExp" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3}/>
                                    <stop offset="95%" stopColor="#ef4444" stopOpacity={0}/>
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" stroke="#292524" />
                            <XAxis dataKey="sim_time_hours" stroke="#57534e" tick={{fontSize: 10}} label={{ value: 'Sim Hours', position: 'insideBottom', offset: -5 }} />
                            <YAxis stroke="#57534e" tick={{fontSize: 10}} />
                            <Tooltip contentStyle={{backgroundColor: '#1c1917', borderColor: '#44403c', fontSize: '12px'}} />
                            <Legend />
                            <Area type="monotone" dataKey="revenue_cum" name="Revenue" stroke="#10b981" fillOpacity={1} fill="url(#colorRev)" />
                            <Area type="monotone" dataKey="expenses_cum" name="Expenses" stroke="#ef4444" fillOpacity={1} fill="url(#colorExp)" />
                        </AreaChart>
                    </ResponsiveContainer>
                </div>

                {/* CHART 2: OEE & SAFETY */}
                <div className="bg-stone-900 border border-stone-800 rounded p-4 h-[350px]">
                    <h3 className="text-sm font-bold text-stone-400 mb-4 font-mono uppercase">Operational Efficiency vs Safety</h3>
                    <ResponsiveContainer width="100%" height="90%">
                        <LineChart data={data}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#292524" />
                            <XAxis dataKey="sim_time_hours" stroke="#57534e" tick={{fontSize: 10}} />
                            <YAxis yAxisId="left" stroke="#f59e0b" domain={[0, 1]} tick={{fontSize: 10}} />
                            <YAxis yAxisId="right" orientation="right" stroke="#3b82f6" domain={[80, 100]} tick={{fontSize: 10}} />
                            <Tooltip contentStyle={{backgroundColor: '#1c1917', borderColor: '#44403c', fontSize: '12px'}} />
                            <Legend />
                            <Line yAxisId="left" type="monotone" dataKey="oee" name="OEE" stroke="#f59e0b" dot={false} strokeWidth={2} />
                            <Line yAxisId="right" type="stepAfter" dataKey="safety_score" name="Safety Score" stroke="#3b82f6" dot={false} strokeWidth={2} />
                        </LineChart>
                    </ResponsiveContainer>
                </div>
                
                {/* CHART 3: ALERTS & INCIDENTS */}
                <div className="bg-stone-900 border border-stone-800 rounded p-4 h-[300px]">
                    <h3 className="text-sm font-bold text-stone-400 mb-4 font-mono uppercase">System Stability (Active Alerts)</h3>
                    <ResponsiveContainer width="100%" height="90%">
                        <BarChart data={data}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#292524" vertical={false} />
                            <XAxis dataKey="sim_time_hours" stroke="#57534e" tick={{fontSize: 10}} />
                            <YAxis stroke="#57534e" tick={{fontSize: 10}} />
                            <Tooltip contentStyle={{backgroundColor: '#1c1917', borderColor: '#44403c', fontSize: '12px'}} />
                            <Bar dataKey="active_alerts" name="Active Alerts" fill="#d97706" />
                            <Bar dataKey="safety_incidents" name="Safety Incidents" fill="#ef4444" />
                        </BarChart>
                    </ResponsiveContainer>
                </div>

                {/* CHART 4: AGENT COST ESTIMATE */}
                <div className="bg-stone-900 border border-stone-800 rounded p-4 h-[300px]">
                    <h3 className="text-sm font-bold text-stone-400 mb-4 font-mono uppercase">Est. Agent Compute Cost ($)</h3>
                    <ResponsiveContainer width="100%" height="90%">
                        <AreaChart data={data}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#292524" />
                            <XAxis dataKey="sim_time_hours" stroke="#57534e" tick={{fontSize: 10}} />
                            <YAxis stroke="#57534e" tick={{fontSize: 10}} />
                            <Tooltip contentStyle={{backgroundColor: '#1c1917', borderColor: '#44403c', fontSize: '12px'}} />
                            <Area type="monotone" dataKey="agent_cost_est" name="Agent Cost ($)" stroke="#8b5cf6" fill="#8b5cf6" fillOpacity={0.2} />
                        </AreaChart>
                    </ResponsiveContainer>
                </div>
            </div>
          )}
        </>
      )}

      {/* ===================== LEARNING TAB ===================== */}
      {activeTab === 'learning' && (
        <>
          {learningLoading && !learningStats ? (
            <div className="h-[400px] w-full flex items-center justify-center text-stone-500 gap-2 border border-stone-800 border-dashed rounded bg-stone-900/20">
                 <FaSpinner className="animate-spin" /> Loading Learning Data...
            </div>
          ) : (
            <>
              {/* STATS CARDS */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                  <StatCard 
                      icon={<FaBrain />} 
                      label="Total Decisions" 
                      value={learningStats?.total_replays || 0} 
                      color="bg-purple-900/30 border-purple-800 text-purple-400"
                  />
                  <StatCard 
                      icon={<FaLightbulb />} 
                      label="Decision Accuracy" 
                      value={`${((learningStats?.accuracy_rate || 0) * 100).toFixed(1)}%`} 
                      color="bg-emerald-900/30 border-emerald-800 text-emerald-400"
                  />
                  <StatCard 
                      icon={<FaChartLine />} 
                      label="Optimal Decisions" 
                      value={learningStats?.optimal_decisions || 0} 
                      color="bg-cyan-900/30 border-cyan-800 text-cyan-400"
                  />
                  <StatCard 
                      icon={<FaHistory />} 
                      label="Policy Updates Pending" 
                      value={learningStats?.policy_updates_recommended || 0} 
                      color="bg-amber-900/30 border-amber-800 text-amber-400"
                  />
              </div>
              
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
                  {/* ACCURACY OVER TIME CHART */}
                  <div className="bg-stone-900 border border-stone-800 rounded p-4 h-[350px]">
                      <h3 className="text-sm font-bold text-stone-400 mb-4 font-mono uppercase flex items-center gap-2">
                          <FaChartLine className="text-purple-400" /> Accuracy Over Time
                      </h3>
                      {accuracyData.length > 0 ? (
                          <ResponsiveContainer width="100%" height="85%">
                              <LineChart data={accuracyData}>
                                  <CartesianGrid strokeDasharray="3 3" stroke="#292524" />
                                  <XAxis dataKey="cumulative_total" stroke="#57534e" tick={{fontSize: 10}} label={{ value: 'Total Decisions', position: 'insideBottom', offset: -5 }} />
                                  <YAxis stroke="#57534e" tick={{fontSize: 10}} domain={[0, 1]} tickFormatter={(v) => `${(v*100).toFixed(0)}%`} />
                                  <Tooltip 
                                      contentStyle={{backgroundColor: '#1c1917', borderColor: '#44403c', fontSize: '12px'}} 
                                      formatter={(value: any) => [`${(value*100).toFixed(1)}%`, 'Accuracy']}
                                  />
                                  <Line type="monotone" dataKey="accuracy" name="Accuracy" stroke="#a855f7" strokeWidth={3} dot={{ fill: '#a855f7', strokeWidth: 2 }} />
                              </LineChart>
                          </ResponsiveContainer>
                      ) : (
                          <div className="h-full flex items-center justify-center text-stone-500 text-sm">
                              No learning data yet. Run the simulation to start learning.
                          </div>
                      )}
                  </div>
                  
                  {/* INSIGHTS LIST */}
                  <div className="bg-stone-900 border border-stone-800 rounded p-4 h-[350px] overflow-hidden flex flex-col">
                      <h3 className="text-sm font-bold text-stone-400 mb-4 font-mono uppercase flex items-center gap-2">
                          <FaLightbulb className="text-amber-400" /> Strategic Insights Learned
                      </h3>
                      <div className="flex-1 overflow-y-auto space-y-2">
                          {insights.length > 0 ? (
                              insights.slice().reverse().map((insight, idx) => (
                                  <div 
                                      key={idx} 
                                      className={`p-3 rounded border ${
                                          insight.was_optimal 
                                              ? 'bg-emerald-950/30 border-emerald-900' 
                                              : 'bg-amber-950/30 border-amber-900'
                                      }`}
                                  >
                                      <p className="text-sm text-stone-200">{insight.insight}</p>
                                      <p className="text-[10px] text-stone-500 mt-1 font-mono">
                                          {insight.incident_id} • {new Date(insight.created_at).toLocaleString()}
                                      </p>
                                  </div>
                              ))
                          ) : (
                              <div className="h-full flex items-center justify-center text-stone-500 text-sm">
                                  No insights yet. The system learns from counterfactual analysis after each decision.
                              </div>
                          )}
                      </div>
                  </div>
              </div>
              
              {/* POLICY EVOLUTION TIMELINE */}
              <div className="bg-stone-900 border border-stone-800 rounded p-6 mb-6">
                  <h3 className="text-sm font-bold text-stone-400 mb-6 font-mono uppercase flex items-center gap-2">
                       <FaHistory className="text-cyan-400" /> Policy Evolution Timeline
                  </h3>
                  
                  {policyHistory.length > 0 ? (
                      <div className="relative border-l-2 border-stone-800 ml-3 space-y-8 pb-4">
                          {policyHistory.slice().reverse().map((policy, idx) => (
                              <div key={idx} className="relative pl-8">
                                  {/* Dot */}
                                  <div className={`absolute -left-[9px] top-0 w-4 h-4 rounded-full border-2 ${
                                      idx === 0 ? 'bg-cyan-500 border-cyan-900 shadow-[0_0_10px_rgba(6,182,212,0.5)]' : 'bg-stone-800 border-stone-600'
                                  }`}></div>
                                  
                                  {/* Content */}
                                  <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                                      <div>
                                          <div className="flex items-center gap-3 mb-1">
                                              <span className={`px-2 py-0.5 rounded textxs font-bold font-mono ${
                                                  idx === 0 ? 'bg-cyan-900/40 text-cyan-300' : 'bg-stone-800 text-stone-400'
                                              }`}>
                                                  {policy.version}
                                              </span>
                                              <span className="text-xs text-stone-500 font-mono">
                                                  {new Date(policy.created_at).toLocaleString()}
                                              </span>
                                          </div>
                                          <p className="text-stone-300 font-medium mb-2">{policy.description}</p>
                                          
                                          {/* Changes */}
                                          {policy.changes && policy.changes.length > 0 && (
                                              <div className="space-y-1">
                                                  {policy.changes.map((change: string, cIdx: number) => (
                                                      <div key={cIdx} className="flex items-start gap-2 text-sm text-stone-400">
                                                          <span className="text-emerald-500 mt-1">●</span>
                                                          <span>{change}</span>
                                                      </div>
                                                  ))}
                                              </div>
                                          )}
                                      </div>
                                      
                                      {/* Reason */}
                                      <div className="bg-stone-950/50 p-3 rounded border border-stone-800/50 max-w-sm">
                                          <p className="text-[10px] text-stone-500 uppercase font-bold mb-1">Trigger Event</p>
                                          <p className="text-xs text-stone-400 italic">"{policy.trigger_event}"</p>
                                      </div>
                                  </div>
                              </div>
                          ))}
                      </div>
                  ) : (
                       <div className="h-32 flex items-center justify-center text-stone-500 text-sm border border-stone-800 border-dashed rounded">
                           System is running on initial baseline policy (v1.0). 
                           <br/>
                           Policy updates occur automatically when decision accuracy drops below threshold.
                       </div>
                  )}
              </div>

              {/* LEARNING EXPLANATION */}
              <div className="bg-gradient-to-r from-purple-950/50 to-stone-900 border border-purple-900/50 rounded p-6">
                  <h3 className="text-lg font-bold text-purple-300 mb-2 flex items-center gap-2">
                      <FaBrain /> How Gemini 3 Learns Over Time
                  </h3>
                  <p className="text-sm text-stone-400 leading-relaxed">
                      After each decision, the system performs a <strong className="text-stone-200">counterfactual analysis</strong>: 
                      "What if we had chosen the second-best hypothesis?" These insights are stored persistently and 
                      <strong className="text-stone-200"> injected into future reasoning prompts</strong>, allowing Gemini 3 to 
                      improve its decision-making over time. When enough suboptimal decisions accumulate, the system 
                      triggers <strong className="text-purple-300">policy evolution</strong> to automatically adjust its 
                      confidence thresholds and framework weights.
                  </p>
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}

const MetricCard = ({ label, value, color }: any) => (
    <div className="flex flex-col items-end">
        <span className="text-[10px] text-stone-500 font-mono uppercase">{label}</span>
        <span className={`text-lg font-bold font-mono tracking-tight ${color}`}>{value}</span>
    </div>
);

const StatCard = ({ icon, label, value, color }: any) => (
    <div className={`${color} border rounded p-4 flex items-center gap-3`}>
        <div className="text-2xl">{icon}</div>
        <div>
            <p className="text-[10px] text-stone-400 font-mono uppercase">{label}</p>
            <p className="text-xl font-bold">{value}</p>
        </div>
    </div>
);
