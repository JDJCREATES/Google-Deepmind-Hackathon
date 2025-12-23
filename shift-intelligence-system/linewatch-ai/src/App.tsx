import { useEffect, useState } from 'react';
import { useStore } from './store/useStore';
import FloorMap from './components/FloorMap';
import SidebarFeed from './components/SidebarFeed';
import AgentFlowGraph from './components/AgentFlowGraph';
import { FaPlay, FaStop, FaBolt, FaNetworkWired } from 'react-icons/fa';
import clsx from 'clsx';
import { api } from './services/api';

function App() {
  const { connectWebSocket, isConnected, toggleSimulation } = useStore();
  const [simStatus, setSimStatus] = useState<{running: boolean, uptime: number} | null>(null);

  useEffect(() => {
    connectWebSocket();
    
    // Poll status occasionally
    const interval = setInterval(async () => {
        try {
            const status = await api.simulation.getStatus();
            setSimStatus({running: status.running, uptime: status.uptime_minutes});
        } catch(e) {/* ignore */}
    }, 2000);
    
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="h-screen w-screen bg-stone-100 flex flex-col text-stone-800 font-sans">
      {/* HEADER */}
      <header className="h-14 bg-white border-b border-stone-200 flex items-center justify-between px-4 shadow-sm z-10">
        <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded bg-primary-500 flex items-center justify-center text-white">
                <FaNetworkWired />
            </div>
            <div>
                <h1 className="font-bold text-lg leading-tight tracking-tight text-stone-900">LINEWATCH AI</h1>
                <p className="text-[10px] text-stone-400 font-mono tracking-wider">GEN-3 • EPISTEMIC • V1.0</p>
            </div>
            
            <div className="h-6 w-px bg-stone-200 mx-2" />
            
            <Badge 
                label={isConnected ? "NEURAL LINK ACTIVE" : "OFFLINE"} 
                type={isConnected ? "success" : "error"} 
            />
             <Badge 
                label={simStatus?.running ? `SIMULATION ACTIVE (${simStatus.uptime}m)` : "SIMULATION PAUSED"} 
                type={simStatus?.running ? "success" : "warning"} 
            />
        </div>

        <div className="flex items-center gap-2">
            <Button 
                onClick={() => api.simulation.injectEvent("fire")}
                icon={<FaBolt />} 
                label="INJECT FAULT" 
                variant="danger"
            />
             <div className="h-6 w-px bg-stone-200 mx-2" />
            <Button 
                onClick={toggleSimulation}
                icon={simStatus?.running ? <FaStop /> : <FaPlay />} 
                label={simStatus?.running ? "STOP SIM" : "START SIM"} 
                variant="primary" 
            />
        </div>
      </header>

      {/* MAIN CONTENT GRID */}
      <main className="flex-1 p-4 grid grid-cols-12 gap-4 overflow-hidden">
        
        {/* LEFT: 2D FLOOR MAP (8 Cols) */}
        <div className="col-span-8 flex flex-col gap-2">
            <div className="bg-white rounded-md border border-stone-200 p-2 shadow-sm flex items-center justify-between">
                 <h2 className="font-bold text-stone-700 text-sm pl-2">PRODUCTION FLOOR: ALPHA</h2>
            </div>
            <div className="flex-1 rounded-md overflow-hidden bg-white shadow-sm border border-stone-200 relative">
                <FloorMap />
            </div>
        </div>

        {/* RIGHT: INTELLIGENCE SIDEBAR (4 Cols) */}
        <div className="col-span-4 flex flex-col gap-4">
            {/* HYPOTHESIS MARKET VISUALIZATION */}
            <div className="h-1/3 bg-stone-900 rounded-md border border-stone-700 shadow-sm p-1 flex flex-col overflow-hidden">
                <h2 className="font-bold text-stone-300 text-xs p-2 flex items-center gap-2">
                    <FaNetworkWired className="text-primary-500"/> AGENT FLOW
                </h2>
                <div className="flex-1">
                    <AgentFlowGraph />
                </div>
            </div>
            
            {/* NEURAL STREAM */}
            <div className="flex-1 min-h-0">
                <SidebarFeed />
            </div>
        </div>

      </main>
    </div>
  );
}

// Subcomponents for styling uniformity
const Badge = ({ label, type }: { label: string, type: 'success'|'warning'|'error' }) => {
    return (
        <span className={clsx(
            "text-[10px] font-bold px-2 py-0.5 rounded border",
            type === 'success' && "bg-emerald-50 text-emerald-700 border-emerald-200",
            type === 'warning' && "bg-amber-50 text-amber-700 border-amber-200",
            type === 'error' && "bg-red-50 text-red-700 border-red-200",
        )}>
            {label}
        </span>
    );
};

const Button = ({ label, icon, onClick, variant = 'default' }: any) => {
    return (
        <button 
            onClick={onClick}
            className={clsx(
                "flex items-center gap-2 px-3 py-1.5 rounded text-xs font-semibold transition-all shadow-sm active:scale-95",
                variant === 'primary' && "bg-primary-500 text-white hover:bg-primary-600",
                variant === 'danger' && "bg-background text-red-600 border border-red-200 hover:bg-red-50",
                variant === 'default' && "bg-white text-stone-600 border border-stone-200 hover:bg-stone-50",
            )}
        >
            {icon} {label}
        </button>
    )
}

export default App;
