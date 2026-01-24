

import { useEffect, useState } from 'react';
import { useStore } from '../store/useStore';
import FloorMap from '../components/FloorMap';
import HierarchicalAgentGraph from '../components/HierarchicalAgentGraph';
import AgentActivityLog from '../components/AgentActivityLog';
import { UsageTimer } from '../components/UsageTimer';
import { FaPlay, FaStop, FaBolt, FaFlask, FaIndustry, FaChartLine, FaList, FaProjectDiagram } from 'react-icons/fa';
import clsx from 'clsx';
import { api } from '../services/api';

export default function DashboardPage() {
  const { connectWebSocket, isConnected, toggleSimulation, financials, kpi } = useStore();
  const [simStatus, setSimStatus] = useState<{running: boolean, uptime: number} | null>(null);
  const [mobileTab, setMobileTab] = useState<'logs' | 'graph'>('logs');

  const handleToggleSimulation = async () => {
    await toggleSimulation();
    // Immediate status refresh to update UI state
    try {
        const status = await api.simulation.getStatus();
        setSimStatus({running: status.running, uptime: status.uptime_minutes});
    } catch(e) {/* ignore */}
  };

  useEffect(() => {
    connectWebSocket();
    
    // Poll simulation status every 30 seconds
    const interval = setInterval(async () => {
        try {
            const status = await api.simulation.getStatus();
            setSimStatus({running: status.running, uptime: status.uptime_minutes});
        } catch(e) {/* ignore */}
    }, 30000);
    
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="h-screen w-screen bg-stone-950 flex flex-col text-stone-200 font-sans overflow-hidden">
      {/* HEADER - Fully Responsive */}
      <header className="min-h-12 bg-stone-900 border-b border-stone-800 flex flex-col md:flex-row items-stretch md:items-center justify-between px-2 md:px-4 py-2 md:py-0 gap-2 md:gap-0 shrink-0">
        {/* Top Row: Branding + Status */}
        <div className="flex items-center justify-between md:justify-start gap-2 md:gap-3">
            <div className="flex items-center gap-2 md:gap-3">
                <div className="w-6 h-6 md:w-8 md:h-8 rounded bg-amber-600 flex items-center justify-center text-white text-xs md:text-base">
                    <FaIndustry />
                </div>
                <div>
                    <h1 className="font-bold text-sm md:text-base leading-tight tracking-tight text-stone-100">LINEWATCH AI</h1>
                    <p className="text-[8px] md:text-[9px] text-stone-500 font-mono tracking-wider">EPISTEMIC REASONING • GEMINI-3</p>
                </div>
            </div>
            
            <div className="flex items-center gap-2">
                <StatusBadge 
                    label={isConnected ? "CONN" : "OFF"} 
                    type={isConnected ? "success" : "error"} 
                />
                <StatusBadge 
                    label={simStatus?.running ? `RUN ${simStatus.uptime}m` : "PAUSE"} 
                    type={simStatus?.running ? "success" : "warning"} 
                />
            </div>
        </div>

      {/* Usage Timer */}
      <div className="hidden md:flex">
        <UsageTimer />
      </div>

      {/* Financial Tracker - Responsive Grid */}
      <div className="flex items-center gap-2 md:gap-4 lg:gap-6 overflow-x-auto no-scrollbar">
        
        {/* KPIs (OEE & Safety) */}
        <div className="flex gap-2 md:gap-4 pr-2 md:pr-4 border-r border-stone-800/50 shrink-0">
            <div className="flex flex-col items-center">
                <span className="text-[8px] md:text-[10px] text-stone-500 font-mono tracking-wider">OEE</span>
                <span className={`font-mono font-bold text-xs md:text-sm lg:text-lg leading-none tabular-nums ${
                    (kpi?.oee ?? 1) >= 0.85 ? 'text-emerald-400' : (kpi?.oee ?? 1) >= 0.60 ? 'text-amber-400' : 'text-rose-400'
                }`}>
                    {((kpi?.oee ?? 1) * 100).toFixed(0)}%
                </span>
            </div>
            
            <div className="flex flex-col items-center">
                <span className="text-[8px] md:text-[10px] text-stone-500 font-mono tracking-wider">SAFE</span>
                <span className={`font-mono font-bold text-xs md:text-sm lg:text-lg leading-none tabular-nums ${
                    (kpi?.safety_score ?? 100) >= 98 ? 'text-emerald-400' : 'text-rose-400'
                }`}>
                    {(kpi?.safety_score ?? 100).toFixed(0)}%
                </span>
            </div>
        </div>

        {/* Balance */}
        <div className="flex flex-col items-center shrink-0">
            <span className="text-[8px] md:text-[10px] text-stone-500 font-mono tracking-wider uppercase">Balance</span>
            <span className={`font-mono font-bold text-xs md:text-sm lg:text-lg leading-none ${financials.balance < 0 ? 'text-red-500' : 'text-emerald-400'}`}>
                ${(financials.balance / 1000).toFixed(0)}k
            </span>
        </div>

        {/* Detailed Stats Block - Hidden on mobile */}
        <div className="hidden md:flex items-center gap-2 lg:gap-4 bg-stone-900/40 py-1 px-2 lg:px-3 rounded border border-stone-800/30 shrink-0">
            {/* Revenue */}
            <div className="flex flex-col">
                <span className="text-[8px] lg:text-[9px] text-stone-600 font-mono uppercase">Rev</span>
                <span className="text-stone-400 font-mono text-[10px] lg:text-xs">
                    +${(financials.total_revenue / 1000).toFixed(0)}k
                </span>
            </div>
            
            <div className="h-4 lg:h-5 w-px bg-stone-800"></div>

            {/* Expenses */}
            <div className="flex flex-col">
                <span className="text-[8px] lg:text-[9px] text-stone-600 font-mono uppercase">Exp</span>
                <span className="text-stone-400 font-mono text-[10px] lg:text-xs">
                    -${(financials.total_expenses / 1000).toFixed(0)}k
                </span>
            </div>
            
            <div className="h-4 lg:h-5 w-px bg-stone-800"></div>

            {/* Burn Rate */}
            <div className="flex flex-col">
                <span className="text-[8px] lg:text-[9px] text-stone-600 font-mono uppercase">Burn</span>
                <span className="text-orange-900/80 font-mono text-[10px] lg:text-xs">
                    -${financials.expenses_per_hour.toFixed(0)}/h
                </span>
            </div>
        </div>
      </div>

        {/* Action Buttons - Responsive */}
        <div className="flex items-center gap-1 md:gap-2">
            <ActionButton 
                onClick={() => window.open('#/analytics', '_blank')}
                icon={<FaChartLine />} 
                label={<span className="hidden md:inline">ANALYTICS</span>}
                variant="default"
            />
            <ActionButton 
                onClick={() => api.simulation.injectEvent("fire")}
                icon={<FaBolt />} 
                label={<span className="hidden md:inline">INJECT</span>}
                variant="danger"
            />
            <ActionButton 
                onClick={handleToggleSimulation}
                icon={simStatus?.running ? <FaStop /> : <FaPlay />} 
                label={simStatus?.running ? "STOP" : "START"} 
                variant="primary" 
            />
        </div>
      </header>

      {/* MAIN GRID - Responsive Layout */}
      <main className="flex-1 flex flex-col p-2 md:p-3 gap-2 md:gap-3 min-h-0 overflow-hidden">
        
        {/* MOBILE: Persistent Map + Tabbed Details */}
        <div className="flex lg:hidden flex-col gap-2 flex-1 min-h-0">
            
            {/* Always Visible Map (Fixed height) */}
            <div className="h-[40vh] min-h-[250px] shrink-0 flex flex-col bg-stone-900 border border-stone-800 rounded-md overflow-hidden">
                <div className="px-2 py-1 bg-stone-900/50 flex items-center justify-between border-b border-stone-800/50">
                    <div className="flex items-center gap-2">
                         <FaIndustry className="text-amber-500 text-[10px]" />
                         <span className="text-[10px] font-bold text-stone-400">LIVE FLOOR</span>
                    </div>
                </div>
                <div className="flex-1 min-h-0 relative">
                    <FloorMap />
                </div>
            </div>

            {/* Tab Navigation */}
            <div className="flex bg-stone-900 border border-stone-800 rounded p-1 shrink-0">
                <button 
                    onClick={() => setMobileTab('logs')}
                    className={`flex-1 py-2 text-xs font-bold rounded flex items-center justify-center gap-2 ${mobileTab === 'logs' ? 'bg-stone-800 text-stone-200' : 'text-stone-500 hover:text-stone-300'}`}
                >
                    <FaList /> LIVE LOGS
                </button>
                <button 
                    onClick={() => setMobileTab('graph')}
                    className={`flex-1 py-2 text-xs font-bold rounded flex items-center justify-center gap-2 ${mobileTab === 'graph' ? 'bg-stone-800 text-stone-200' : 'text-stone-500 hover:text-stone-300'}`}
                >
                    <FaProjectDiagram /> AGENT GRAPH
                </button>
            </div>

            {/* Mobile Content Area */}
            <div className="flex-1 min-h-0 relative flex flex-col">
                {mobileTab === 'logs' && (
                     <div className="flex-1 min-h-0">
                        <AgentActivityLog />
                     </div>
                )}
                {mobileTab === 'graph' && (
                    <div className="flex-1 min-h-0 bg-stone-950 border border-stone-800 rounded-md overflow-hidden">
                         <HierarchicalAgentGraph />
                    </div>
                )}
            </div>
        </div>

        {/* DESKTOP: Original layout - Top row (floor + activity), bottom row (graph) */}
        <div className="hidden lg:flex flex-col gap-3 flex-1 min-h-0">
          
          {/* TOP ROW: Floor Map + Activity Log side-by-side */}
          <div className="flex gap-3 flex-1 min-h-0">
            
            {/* FLOOR MAP - 75% width */}
            <div className="flex flex-col" style={{ width: '75%' }}>
              <div className="bg-stone-900 border border-stone-800 rounded-t-md px-3 py-1.5 flex items-center gap-2">
                  <FaIndustry className="text-amber-500 text-xs" />
                  <h2 className="font-semibold text-stone-300 text-xs tracking-wide">PRODUCTION FLOOR</h2>
              </div>
              <div className="flex-1 rounded-b-md overflow-hidden bg-stone-900 border-x border-b border-stone-800 min-h-0">
                  <FloorMap />
              </div>
            </div>

            {/* ACTIVITY LOG - 25% width */}
            <div className="flex-1 flex flex-col min-h-0">
              <AgentActivityLog />
            </div>
          </div>

          {/* BOTTOM ROW: Reasoning Graph */}
          <div className="h-[400px] shrink-0 overflow-hidden bg-stone-950 border border-stone-800 rounded-md">
              <HierarchicalAgentGraph />
          </div>
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

// Action button component - Responsive
const ActionButton = ({ label, icon, onClick, variant = 'default' }: any) => {
    return (
        <button 
            onClick={onClick}
            className={clsx(
                "flex items-center gap-1 md:gap-1.5 px-2 md:px-3 py-1 md:py-1.5 rounded text-[10px] md:text-xs font-semibold transition-all active:scale-95",
                variant === 'primary' && "bg-amber-600 text-white hover:bg-amber-500",
                variant === 'danger' && "bg-transparent text-red-400 border border-red-800 hover:bg-red-950",
                variant === 'default' && "bg-stone-800 text-stone-300 border border-stone-700 hover:bg-stone-700",
            )}
        >
            {icon} {label}
        </button>
    )
}
