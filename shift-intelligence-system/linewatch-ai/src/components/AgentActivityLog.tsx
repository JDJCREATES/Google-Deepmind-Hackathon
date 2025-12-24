import React, { useState } from 'react';
import { useStore } from '../store/useStore';
import { FaRobot } from 'react-icons/fa';

type AgentTab = 'all' | 'orchestrator' | 'production' | 'compliance' | 'staffing' | 'maintenance';

const AGENT_TABS: { id: AgentTab; label: string; color: string }[] = [
    { id: 'all', label: 'All', color: '#A1A1AA' },
    { id: 'orchestrator', label: 'Orchestrator', color: '#F59E0B' },
    { id: 'production', label: 'Production', color: '#3B82F6' },
    { id: 'compliance', label: 'Compliance', color: '#10B981' },
    { id: 'staffing', label: 'Staffing', color: '#8B5CF6' },
    { id: 'maintenance', label: 'Maintenance', color: '#EF4444' },
];

const AgentActivityLog: React.FC = () => {
    const { logs } = useStore();
    const [activeTab, setActiveTab] = useState<AgentTab>('all');
    
    // Filter logs by type and agent
    const agentLogs = logs.filter(log => {
        const isAgentEvent = log.type === 'agent_activity' || log.type === 'agent_thinking';
        if (!isAgentEvent) return false;
        
        if (activeTab === 'all') return true;
        
        const source = (log.source || '').toLowerCase();
        if (activeTab === 'orchestrator') return source.includes('orchestrator') || source.includes('master');
        return source.includes(activeTab);
    });
    
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
                        Agent Activity
                    </h2>
                </div>
            </div>
            
            {/* Agent Tabs */}
            <div className="flex gap-1 px-2 py-2 bg-stone-900/50 border-b border-stone-800 overflow-x-auto">
                {AGENT_TABS.map(tab => {
                    const isActive = activeTab === tab.id;
                    const count = tab.id === 'all' ? agentLogs.length : 
                        logs.filter(l => {
                            const s = (l.source || '').toLowerCase();
                            if (tab.id === 'orchestrator') return s.includes('orchestrator') || s.includes('master');
                            return s.includes(tab.id);
                        }).length;
                    
                    return (
                        <button
                            key={tab.id}
                            onClick={() => setActiveTab(tab.id)}
                            className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all whitespace-nowrap ${
                                isActive 
                                    ? 'text-white shadow-lg' 
                                    : 'text-stone-400 hover:text-stone-200 hover:bg-stone-800'
                            }`}
                            style={{
                                backgroundColor: isActive ? tab.color + '30' : 'transparent',
                                borderWidth: '1px',
                                borderStyle: 'solid',
                                borderColor: isActive ? tab.color : 'transparent',
                            }}
                        >
                            {tab.label}
                            {count > 0 && (
                                <span className="ml-1.5 text-[10px] opacity-70">({count})</span>
                            )}
                        </button>
                    );
                })}
            </div>

            {/* Log Entries */}
            <div className="flex-1 overflow-y-auto">
                {agentLogs.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-stone-500 text-sm gap-2">
                        <FaRobot size={24} className="opacity-30" />
                        <span>No activity for {activeTab === 'all' ? 'any agent' : activeTab}...</span>
                    </div>
                ) : (
                    <div className="divide-y divide-stone-800/50">
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
