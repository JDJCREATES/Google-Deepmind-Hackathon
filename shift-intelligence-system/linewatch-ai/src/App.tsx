import { useEffect, useState } from 'react';
import { useStore } from './store/useStore';
import FloorMap from './components/FloorMap';
import AgentReasoningGraph from './components/AgentReasoningGraph';
import AgentActivityLog from './components/AgentActivityLog';
import { FaPlay, FaStop, FaBolt, FaNetworkWired, FaIndustry } from 'react-icons/fa';
import clsx from 'clsx';
import { api } from './services/api';

function App() {
  const { connectWebSocket, isConnected, toggleSimulation } = useStore();
  const [simStatus, setSimStatus] = useState<{running: boolean, uptime: number} | null>(null);

  useEffect(() => {
    connectWebSocket();
    
    const interval = setInterval(async () => {
        try {
            const status = await api.simulation.getStatus();
            setSimStatus({running: status.running, uptime: status.uptime_minutes});
        } catch(e) {/* ignore */}
    }, 2000);
    
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="h-screen w-screen bg-stone-950 flex flex-col text-stone-200 font-sans overflow-hidden">
      {/* HEADER */}
      <header className="h-12 bg-stone-900 border-b border-stone-800 flex items-center justify-between px-4 shrink-0">
        <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded bg-amber-600 flex items-center justify-center text-white">
                <FaIndustry />
            </div>
            <div>
                <h1 className="font-bold text-base leading-tight tracking-tight text-stone-100">LINEWATCH AI</h1>
                <p className="text-[9px] text-stone-500 font-mono tracking-wider">EPISTEMIC REASONING • GEN-3</p>
            </div>
            
            <div className="h-6 w-px bg-stone-700 mx-3" />
            
            <StatusBadge 
                label={isConnected ? "CONNECTED" : "OFFLINE"} 
                type={isConnected ? "success" : "error"} 
            />
            <StatusBadge 
                label={simStatus?.running ? `ACTIVE ${simStatus.uptime}m` : "PAUSED"} 
                type={simStatus?.running ? "success" : "warning"} 
            />
        </div>

        <div className="flex items-center gap-2">
            <ActionButton 
                onClick={() => api.simulation.injectEvent("fire")}
                icon={<FaBolt />} 
                label="INJECT FAULT" 
                variant="danger"
            />
            <ActionButton 
                onClick={toggleSimulation}
                icon={simStatus?.running ? <FaStop /> : <FaPlay />} 
                label={simStatus?.running ? "STOP" : "START"} 
                variant="primary" 
            />
        </div>
      </header>

      {/* MAIN GRID: Top Row = Floor + Activity Log, Bottom Row = Reasoning Graph */}
      <main className="flex-1 flex flex-col p-3 gap-3 min-h-0">
        
        {/* TOP ROW: Floor Map + Activity Log */}
        <div className="flex gap-3 flex-1 min-h-0">
          
          {/* FLOOR MAP - Priority: always fully visible */}
          <div className="flex flex-col shrink-0" style={{ width: '75%' }}>
            <div className="bg-stone-900 border border-stone-800 rounded-t-md px-3 py-1.5 flex items-center gap-2">
                <FaIndustry className="text-amber-500 text-xs" />
                <h2 className="font-semibold text-stone-300 text-xs tracking-wide">PRODUCTION FLOOR</h2>
            </div>
            <div className="flex-1 rounded-b-md overflow-hidden bg-stone-900 border-x border-b border-stone-800">
                <FloorMap />
            </div>
          </div>

          {/* ACTIVITY LOG - Right side */}
          <div className="flex-1 min-w-[280px] flex flex-col min-h-0">
            <AgentActivityLog />
          </div>
        </div>

        {/* BOTTOM ROW: Agent Reasoning Graph */}
        <div className="h-[400px] shrink-0 overflow-hidden bg-stone-950 border border-stone-800 rounded-md">
            <AgentReasoningGraph />
        </div>
      </main>
    </div>
  );
}

// Enterprise-style status badge
const StatusBadge = ({ label, type }: { label: string, type: 'success'|'warning'|'error' }) => {
    return (
        <span className={clsx(
            "text-[10px] font-bold px-2 py-0.5 rounded flex items-center gap-1",
            type === 'success' && "bg-emerald-950 text-emerald-400 border border-emerald-800",
            type === 'warning' && "bg-amber-950 text-amber-400 border border-amber-800",
            type === 'error' && "bg-red-950 text-red-400 border border-red-800",
        )}>
            <span className={clsx(
                "w-1.5 h-1.5 rounded-full",
                type === 'success' && "bg-emerald-400",
                type === 'warning' && "bg-amber-400",
                type === 'error' && "bg-red-400",
            )} />
            {label}
        </span>
    );
};

// Action button component
const ActionButton = ({ label, icon, onClick, variant = 'default' }: any) => {
    return (
        <button 
            onClick={onClick}
            className={clsx(
                "flex items-center gap-1.5 px-3 py-1 rounded text-xs font-semibold transition-all active:scale-95",
                variant === 'primary' && "bg-amber-600 text-white hover:bg-amber-500",
                variant === 'danger' && "bg-transparent text-red-400 border border-red-800 hover:bg-red-950",
                variant === 'default' && "bg-stone-800 text-stone-300 border border-stone-700 hover:bg-stone-700",
            )}
        >
            {icon} {label}
        </button>
    )
}

export default App;
