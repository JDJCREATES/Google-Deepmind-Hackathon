import React from 'react';
import { useStore, type LogEntry } from '../store/useStore';
import { FaRobot } from 'react-icons/fa';

const AgentActivityLog: React.FC = () => {
    const { logs } = useStore();
    
    // Filter to only show agent_activity and agent_thinking events
    const agentLogs = logs.filter(log => 
        log.type === 'agent_activity' || log.type === 'agent_thinking'
    );
    
    const getAgentColor = (source: string) => {
        const s = source.toLowerCase();
        if (s.includes('orchestrator') || s.includes('master')) return '#F59E0B';
        if (s.includes('production')) return '#3B82F6';
        if (s.includes('compliance')) return '#10B981';
        if (s.includes('staffing')) return '#8B5CF6';
        if (s.includes('maintenance')) return '#EF4444';
        return '#6B7280';
    };

    return (
        <div className="h-full flex flex-col bg-stone-950 border border-stone-800 rounded-lg overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-stone-900 to-stone-800 border-b border-stone-700">
                <div className="flex items-center gap-2">
                    <FaRobot className="text-amber-500" size={20} />
                    <h2 className="text-sm font-bold text-stone-100 uppercase tracking-wide">
                        Agent Activity Log
                    </h2>
                </div>
                <div className="flex items-center gap-2">
                    <span className="text-xs text-stone-400">{agentLogs.length} events</span>
                    <div className="flex items-center gap-1">
                        <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                        <span className="text-xs text-green-400 font-semibold">LIVE</span>
                    </div>
                </div>
            </div>

            {/* Log Entries */}
            <div className="flex-1 overflow-y-auto">
                {agentLogs.length === 0 ? (
                    <div className="flex items-center justify-center h-full text-stone-500 text-sm">
                        No agent activity yet...
                    </div>
                ) : (
                    <div className="divide-y divide-stone-800">
                        {agentLogs.map((entry) => {
                            const agentColor = getAgentColor(entry.source || 'System');
                            const timestamp = new Date(entry.timestamp).toLocaleTimeString();
                            
                            return (
                                <div
                                    key={entry.id}
                                    className="px-4 py-3 hover:bg-stone-900/50 transition-colors"
                                    style={{ borderLeftWidth: '3px', borderLeftColor: agentColor }}
                                >
                                    {/* Agent & Time */}
                                    <div className="flex items-center justify-between mb-1">
                                        <span 
                                            className="text-xs font-bold uppercase tracking-wide"
                                            style={{ color: agentColor }}
                                        >
                                            {entry.source || 'System'}
                                        </span>
                                        <span className="text-[10px] text-stone-500 font-mono">
                                            {timestamp}
                                        </span>
                                    </div>
                                    
                                    {/* Message */}
                                    <p className="text-sm text-stone-300 leading-relaxed">
                                        {entry.description}
                                    </p>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        </div>
    );
};

export default AgentActivityLog;
