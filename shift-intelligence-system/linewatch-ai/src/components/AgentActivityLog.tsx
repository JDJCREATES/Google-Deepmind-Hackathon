import React, { useState } from 'react';
import { useStore } from '../store/useStore';
import { FaRobot, FaCog, FaLightbulb, FaSearch, FaBalanceScale, FaBolt, FaChevronDown, FaChevronRight } from 'react-icons/fa';
import { MdPsychology } from 'react-icons/md';

interface ReasoningEvent {
    id: string;
    timestamp: string;
    agent: string;
    phase: string;
    type: 'hypothesis' | 'evidence' | 'belief' | 'action' | 'decision' | 'system';
    title: string;
    details?: string;
    data?: any;
}

const AgentActivityLog: React.FC = () => {
    const { logs } = useStore();
    const [expandedEvents, setExpandedEvents] = useState<Set<string>>(new Set());
    
    // Parse logs into structured events
    const events: ReasoningEvent[] = logs.slice(0, 50).map((log, i) => {
        const timestamp = new Date().toLocaleTimeString();
        
        // Parse event type from log content
        let type: ReasoningEvent['type'] = 'system';
        let phase = 'SYSTEM';
        let agent = 'System';
        let title = log;
        
        const logLower = log.toLowerCase();
        
        if (logLower.includes('hypothesis')) {
            type = 'hypothesis';
            phase = 'HYPOTHESIS GENERATION';
        } else if (logLower.includes('evidence')) {
            type = 'evidence';
            phase = 'EVIDENCE GATHERING';
        } else if (logLower.includes('belief')) {
            type = 'belief';
            phase = 'BELIEF UPDATE';
        } else if (logLower.includes('action') || logLower.includes('execute')) {
            type = 'action';
            phase = 'ACTION EXECUTION';
        } else if (logLower.includes('decision') || logLower.includes('select')) {
            type = 'decision';
            phase = 'DECISION';
        }
        
        if (logLower.includes('production')) agent = 'Production Agent';
        else if (logLower.includes('compliance')) agent = 'Compliance Agent';
        else if (logLower.includes('staffing')) agent = 'Staffing Agent';
        else if (logLower.includes('maintenance')) agent = 'Maintenance Agent';
        else if (logLower.includes('orchestrator')) agent = 'Orchestrator';
        
        return {
            id: `event-${i}`,
            timestamp,
            agent,
            phase,
            type,
            title: title.split('] ')[1] || title,
            details: undefined,
        };
    });
    
    const toggleExpand = (id: string) => {
        setExpandedEvents(prev => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });
    };
    
    const getIcon = (type: ReasoningEvent['type']) => {
        switch (type) {
            case 'hypothesis': return <FaLightbulb className="text-blue-400" />;
            case 'evidence': return <FaSearch className="text-green-400" />;
            case 'belief': return <MdPsychology className="text-orange-400" />;
            case 'action': return <FaBolt className="text-pink-400" />;
            case 'decision': return <FaBalanceScale className="text-amber-400" />;
            default: return <FaCog className="text-stone-400" />;
        }
    };
    
    const getTypeStyle = (type: ReasoningEvent['type']) => {
        switch (type) {
            case 'hypothesis': return 'border-l-blue-500 bg-blue-950/30';
            case 'evidence': return 'border-l-green-500 bg-green-950/30';
            case 'belief': return 'border-l-orange-500 bg-orange-950/30';
            case 'action': return 'border-l-pink-500 bg-pink-950/30';
            case 'decision': return 'border-l-amber-500 bg-amber-950/30';
            default: return 'border-l-stone-500 bg-stone-900/30';
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
                    <span className="hidden sm:inline">{events.length} events</span>
                    <span className="flex items-center gap-1">
                        <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
                        LIVE
                    </span>
                </div>
            </div>
            
            {/* Column Headers - Hidden on small screens */}
            <div className="hidden lg:grid grid-cols-12 gap-2 px-4 py-2 bg-stone-900/50 border-b border-stone-800 text-xs font-semibold text-stone-500 uppercase tracking-wider shrink-0">
                <div className="col-span-1">Time</div>
                <div className="col-span-2">Agent</div>
                <div className="col-span-2">Phase</div>
                <div className="col-span-7">Event</div>
            </div>
            
            {/* Events List */}
            <div className="flex-1 overflow-y-auto">
                {events.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-stone-600">
                        <FaRobot className="text-4xl mb-2 opacity-30" />
                        <p className="text-sm">Waiting for agent activity...</p>
                        <p className="text-xs mt-1">Click "Inject Fault" to trigger reasoning</p>
                    </div>
                ) : (
                    events.map((event) => (
                        <div
                            key={event.id}
                            className={`border-l-4 ${getTypeStyle(event.type)} border-b border-stone-800/50 hover:bg-stone-800/30 transition-colors`}
                        >
                            <div
                                className="px-4 py-3 cursor-pointer"
                                onClick={() => toggleExpand(event.id)}
                            >
                                {/* Mobile/Tablet Layout */}
                                <div className="lg:hidden space-y-2">
                                    <div className="flex items-start justify-between gap-2">
                                        <div className="flex items-center gap-2 min-w-0 flex-1">
                                            {getIcon(event.type)}
                                            <span className="text-xs text-stone-300 font-medium break-words">
                                                {event.agent}
                                            </span>
                                        </div>
                                        <span className="text-xs text-stone-500 font-mono shrink-0">
                                            {event.timestamp.split(':').slice(0, 2).join(':')}
                                        </span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <span className={`px-2 py-1 rounded text-[10px] font-bold uppercase tracking-wide shrink-0 ${
                                            event.type === 'hypothesis' ? 'bg-blue-900/50 text-blue-300' :
                                            event.type === 'evidence' ? 'bg-green-900/50 text-green-300' :
                                            event.type === 'belief' ? 'bg-orange-900/50 text-orange-300' :
                                            event.type === 'action' ? 'bg-pink-900/50 text-pink-300' :
                                            event.type === 'decision' ? 'bg-amber-900/50 text-amber-300' :
                                            'bg-stone-800 text-stone-400'
                                        }`}>
                                            {event.phase}
                                        </span>
                                    </div>
                                    <div className="text-xs text-stone-300 break-words pl-6">
                                        {event.title}
                                    </div>
                                </div>

                                {/* Desktop Layout */}
                                <div className="hidden lg:grid lg:grid-cols-12 gap-3 items-center">
                                    <div className="col-span-1 text-xs text-stone-500 font-mono shrink-0">
                                        {event.timestamp.split(':').slice(0, 2).join(':')}
                                    </div>
                                    <div className="col-span-2 text-xs text-stone-300 font-medium break-words">
                                        {event.agent}
                                    </div>
                                    <div className="col-span-2 text-xs">
                                        <span className={`px-2 py-1 rounded text-[10px] font-bold uppercase tracking-wide inline-block ${
                                            event.type === 'hypothesis' ? 'bg-blue-900/50 text-blue-300' :
                                            event.type === 'evidence' ? 'bg-green-900/50 text-green-300' :
                                            event.type === 'belief' ? 'bg-orange-900/50 text-orange-300' :
                                            event.type === 'action' ? 'bg-pink-900/50 text-pink-300' :
                                            event.type === 'decision' ? 'bg-amber-900/50 text-amber-300' :
                                            'bg-stone-800 text-stone-400'
                                        }`}>
                                            {event.phase}
                                        </span>
                                    </div>
                                    <div className="col-span-7 flex items-center gap-2 text-xs text-stone-300 min-w-0">
                                        {getIcon(event.type)}
                                        <span className="break-words flex-1">{event.title}</span>
                                        {event.details && (
                                            expandedEvents.has(event.id) 
                                                ? <FaChevronDown className="text-stone-500 shrink-0" />
                                                : <FaChevronRight className="text-stone-500 shrink-0" />
                                        )}
                                    </div>
                                </div>
                            </div>
                            
                            {/* Expanded Details */}
                            {expandedEvents.has(event.id) && event.details && (
                                <div className="px-4 py-3 bg-stone-900/50 border-t border-stone-800/50">
                                    <pre className="text-xs text-stone-400 font-mono whitespace-pre-wrap break-words">
                                        {event.details}
                                    </pre>
                                </div>
                            )}
                        </div>
                    ))
                )}
            </div>
        </div>
    );
};

export default AgentActivityLog;

