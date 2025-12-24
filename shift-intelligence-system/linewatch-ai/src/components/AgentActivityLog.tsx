import React, { useState } from 'react';
import { useStore, type LogEntry } from '../store/useStore';
import { FaRobot, FaCog, FaLightbulb, FaSearch, FaBolt, FaChessBoard, FaExclamationTriangle, FaChevronRight, FaChevronDown } from 'react-icons/fa';
import { MdPsychology, MdHealthAndSafety } from 'react-icons/md';

const AgentActivityLog: React.FC = () => {
    const { logs } = useStore();
    const [expandedEvents, setExpandedEvents] = useState<Set<string>>(new Set());
    
    const toggleExpand = (id: string) => {
        setExpandedEvents(prev => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });
    };
    
    // Map backend event types to UI icons/styles
    const getEventMeta = (entry: LogEntry) => {
        switch (entry.type) {
            case 'visual_signal':
                return { 
                    icon: <FaExclamationTriangle className="text-red-500" />, 
                    color: 'border-l-red-500 bg-red-950/20',
                    phase: 'DETECTION',
                    label: 'Visual Signal'
                };
            case 'investigation_start':
                return { 
                    icon: <FaBolt className="text-yellow-500" />, 
                    color: 'border-l-yellow-500 bg-yellow-950/20',
                    phase: 'ALERT',
                    label: 'Investigation Triggered'
                };
            case 'reasoning_phase':
                return { 
                    icon: <FaChessBoard className="text-purple-400" />, 
                    color: 'border-l-purple-500 bg-purple-950/20',
                    phase: 'ORCHESTRATION',
                    label: 'Phase Change'
                };
             case 'hypotheses_generated':
                return { 
                    icon: <FaLightbulb className="text-blue-400" />, 
                    color: 'border-l-blue-500 bg-blue-950/20',
                    phase: 'HYPOTHESIS',
                    label: 'Hypothesis Generation'
                };
            case 'evidence':
                return { 
                    icon: <FaSearch className="text-green-400" />, 
                    color: 'border-l-green-500 bg-green-950/20',
                    phase: 'EVIDENCE',
                    label: 'Evidence Gathering'
                };
            case 'belief':
                return { 
                    icon: <MdPsychology className="text-orange-400" />, 
                    color: 'border-l-orange-500 bg-orange-950/20',
                    phase: 'REASONING',
                    label: 'Belief Update'
                };
            case 'action':
                return { 
                    icon: <MdHealthAndSafety className="text-pink-400" />, 
                    color: 'border-l-pink-500 bg-pink-950/20',
                    phase: 'ACTION',
                    label: 'Action Selection'
                };
            case 'agent_thought':
                return { 
                    icon: <FaRobot className="text-indigo-400" />, 
                    color: 'border-l-indigo-500 bg-indigo-950/20',
                    phase: 'AGENT',
                    label: 'Agent Thought'
                };
            default:
                return { 
                    icon: <FaCog className="text-stone-400" />, 
                    color: 'border-l-stone-500 bg-stone-900/30',
                    phase: 'SYSTEM',
                    label: 'System'
                };
        }
    };

    return (
        <div className="h-full flex flex-col bg-stone-950 border border-stone-800 rounded-md overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 bg-stone-900 border-b border-stone-800 shrink-0">
                <div className="flex items-center gap-2">
                    <FaRobot className="text-amber-500 shrink-0" />
                    <h2 className="font-bold text-stone-200 text-sm tracking-wide">AGENT ACTIVITY LOG</h2>
                </div>
                <div className="flex items-center gap-4 text-xs text-stone-500">
                    <span className="hidden sm:inline">{logs.length} events</span>
                    <span className="flex items-center gap-1">
                        <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
                        LIVE
                    </span>
                </div>
            </div>
            
            {/* Column Headers */}
            <div className="hidden lg:grid grid-cols-12 gap-2 px-4 py-2 bg-stone-900/50 border-b border-stone-800 text-xs font-semibold text-stone-500 uppercase tracking-wider shrink-0">
                <div className="col-span-3">Time/Agent</div>
                <div className="col-span-3">Phase</div>
                <div className="col-span-6">Event Details</div>
            </div>
            
            {/* Events List */}
            <div className="flex-1 overflow-y-auto scrollbar-thin scrollbar-thumb-stone-800">
                {logs.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-stone-600">
                        <FaRobot className="text-4xl mb-2 opacity-30" />
                        <p className="text-sm">Waiting for agent activity...</p>
                        <p className="text-xs mt-1">Click "Inject Fault" to trigger reasoning</p>
                    </div>
                ) : (
                    logs.map((entry) => {
                        const meta = getEventMeta(entry);
                        const isExpanded = expandedEvents.has(entry.id);
                        const hasDetails = !!entry.data && Object.keys(entry.data).length > 0;
                        
                        return (
                            <div
                                key={entry.id}
                                className={`border-l-4 ${meta.color} border-b border-stone-800/50 hover:bg-stone-800/40 transition-colors`}
                            >
                                <div
                                    className="px-4 py-3 cursor-pointer group"
                                    onClick={() => hasDetails && toggleExpand(entry.id)}
                                >
                                    {/* Desktop Layout */}
                                    <div className="hidden lg:grid grid-cols-12 gap-3 items-start">
                                        {/* Time & Agent */}
                                        <div className="col-span-3 min-w-0">
                                            <div className="text-xs text-stone-500 font-mono mb-0.5">{entry.timestamp}</div>
                                            <div className="text-xs font-bold text-stone-300 truncate" title={entry.source}>
                                                {entry.source || 'System'}
                                            </div>
                                        </div>
                                        
                                        {/* Phase Badge */}
                                        <div className="col-span-3">
                                            <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-stone-900/50 text-stone-400 border border-stone-800`}>
                                                {meta.phase}
                                            </span>
                                        </div>
                                        
                                        {/* Content */}
                                        <div className="col-span-6">
                                            <div className="flex items-start gap-2">
                                                <div className="mt-0.5 shrink-0 opacity-80 group-hover:opacity-100 transition-opacity">
                                                    {meta.icon}
                                                </div>
                                                <div className="flex-1 min-w-0">
                                                    <div className="text-sm text-stone-200 font-medium leading-tight">
                                                        {entry.description}
                                                    </div>
                                                    
                                                    {hasDetails && (
                                                        <div className="mt-1 flex items-center gap-1 text-[10px] text-stone-500 font-medium uppercase tracking-wide group-hover:text-amber-500/80 transition-colors">
                                                            {isExpanded ? <FaChevronDown /> : <FaChevronRight />}
                                                            {isExpanded ? 'Hide Details' : 'View Details'}
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Mobile/Tablet Layout (Simplified) */}
                                    <div className="lg:hidden flex flex-col gap-2">
                                        <div className="flex items-center justify-between text-xs text-stone-500">
                                            <span className="font-mono">{entry.timestamp}</span>
                                            <span className="font-bold text-stone-400">{entry.source}</span>
                                        </div>
                                        <div className="flex items-start gap-3">
                                            <div className="mt-0.5 text-lg">{meta.icon}</div>
                                            <div className="flex-1">
                                                <div className="text-sm text-stone-200 leading-snug">
                                                    {entry.description}
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                
                                {/* Expanded Details View */}
                                {isExpanded && hasDetails && (
                                    <div className="px-4 pb-3 pl-14">
                                        <div className="bg-stone-950 rounded p-3 text-xs font-mono text-stone-400 border border-stone-800/50 shadow-inner overflow-x-auto">
                                            <pre className="whitespace-pre-wrap break-all">
                                                {JSON.stringify(entry.data, null, 2)}
                                            </pre>
                                        </div>
                                    </div>
                                )}
                            </div>
                        );
                    })
                )}
            </div>
        </div>
    );
};

export default AgentActivityLog;
