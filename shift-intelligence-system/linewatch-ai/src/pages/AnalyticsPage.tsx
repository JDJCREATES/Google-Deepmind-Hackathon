
import { useEffect, useState } from 'react';
import { 
  LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  BarChart, Bar
} from 'recharts';
import { FaDownload, FaFlask, FaSpinner, FaHistory } from 'react-icons/fa';

interface ExperimentSession {
    filename: string;
    created_at: string;
    size_bytes: number;
    is_current: boolean;
}

export default function AnalyticsPage() {
  const [data, setData] = useState<any[]>([]);
  const [sessions, setSessions] = useState<ExperimentSession[]>([]);
  const [selectedSession, setSelectedSession] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // 1. Fetch available sessions on mount
  useEffect(() => {
    const fetchSessions = async () => {
        try {
            const res = await fetch('http://localhost:8000/api/experiment/sessions');
            const json = await res.json();
            setSessions(json);
            
            // Auto-select current or latest
            if (json.length > 0 && !selectedSession) {
                const current = json.find((s: any) => s.is_current) || json[0];
                setSelectedSession(current.filename);
            }
        } catch (e) {
            console.error("Failed to fetch sessions", e);
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
            const res = await fetch(`http://localhost:8000/api/experiment/stats?limit=1000&filename=${selectedSession}`);
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


  // Calculate summaries
  const latest = data[data.length - 1] || {};
  const totalRevenue = latest.revenue_cum || 0;
  const totalCost = latest.expenses_cum || 0;
  const roi = totalCost > 0 ? ((totalRevenue - totalCost) / totalCost * 100).toFixed(1) : "0.0";
  
  const currentSessionObj = sessions.find(s => s.filename === selectedSession);

  return (
    <div className="min-h-screen bg-stone-950 text-stone-200 font-sans p-6 overflow-auto">
      {/* HEADER */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between mb-8 border-b border-stone-800 pb-4 gap-4">
        <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-cyan-900/30 rounded flex items-center justify-center text-cyan-400 border border-cyan-800">
                <FaFlask />
            </div>
            <div>
                <h1 className="text-xl font-bold text-stone-100 tracking-tight">EXPERIMENT ANALYTICS</h1>
                <p className="text-[10px] text-stone-500 font-mono uppercase tracking-wider flex items-center gap-2">
                   <span>GEMINI-3 AGENT ROI ANALYSIS</span>
                   {currentSessionObj?.is_current && <span className="text-emerald-500 animate-pulse">● LIVE RECORDING</span>}
                </p>
            </div>
        </div>
        
        {/* CONTROLS */}
        <div className="flex flex-wrap items-center gap-4">
            {/* Session Selector */}
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
                href={`http://localhost:8000/api/experiment/download?filename=${selectedSession}`} 
                target="_blank"
                className="flex items-center gap-2 bg-stone-800 hover:bg-stone-700 text-stone-300 px-4 py-2 rounded text-sm font-semibold border border-stone-700 transition"
                download
            >
                <FaDownload /> CSV
            </a>
        </div>
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
    </div>
  );
}

const MetricCard = ({ label, value, color }: any) => (
    <div className="flex flex-col items-end">
        <span className="text-[10px] text-stone-500 font-mono uppercase">{label}</span>
        <span className={`text-lg font-bold font-mono tracking-tight ${color}`}>{value}</span>
    </div>
);
