import React, { memo } from 'react';
import { Handle, Position } from 'reactflow';
import { FaCog, FaUserShield, FaUsers, FaWrench, FaIndustry, FaBrain, FaLink, FaBolt } from 'react-icons/fa';

interface RichAgentNodeProps {
    data: {
        agentId: string;
        label: string;
        type: 'orchestrator' | 'production' | 'compliance' | 'staffing' | 'maintenance';
        status?: string;
        thoughts?: string[];
        activeTool?: string;
        isActive?: boolean;
        inputTokens?: number;
        outputTokens?: number;
        thoughtSignatures?: number;  // Count of reasoning states
        lastAction?: string;
    };
}

const agentConfig: Record<string, { icon: React.ReactNode; color: string; eyeColor: string }> = {
    orchestrator: {
        icon: <FaBrain size={24} />,
        color: '#F59E0B',
        eyeColor: '#FCD34D',
    },
    production: {
        icon: <FaIndustry size={22} />,
        color: '#3B82F6',
        eyeColor: '#93C5FD',
    },
    compliance: {
        icon: <FaUserShield size={22} />,
        color: '#10B981',
        eyeColor: '#6EE7B7',
    },
    staffing: {
        icon: <FaUsers size={22} />,
        color: '#8B5CF6',
        eyeColor: '#C4B5FD',
    },
    maintenance: {
        icon: <FaWrench size={22} />,
        color: '#EF4444',
        eyeColor: '#FCA5A5',
    },
};

const RichAgentNode: React.FC<RichAgentNodeProps> = memo(({ data }) => {
    const config = agentConfig[data.type] || agentConfig.production;
    const isActive = data.isActive;
    const isOrchestrator = data.type === 'orchestrator';

    // Orchestrator always full opacity, domain agents dull when idle
    const nodeOpacity = isOrchestrator ? 1 : (isActive ? 1 : 0.5);

    return (
        <div
            className={`relative transition-all duration-500 ${isActive ? 'scale-105' : ''}`}
            style={{
                filter: isActive ? `drop-shadow(0 0 20px ${config.color})` : 'none',
                opacity: nodeOpacity,
            }}
        >
            {/* Connection Handles */}
            <Handle type="target" position={Position.Top} className="!bg-stone-600 !w-3 !h-3" />
            <Handle type="source" position={Position.Bottom} className="!bg-stone-600 !w-3 !h-3" />

            {/* Robot Head Container */}
            <div
                className="flex flex-col items-center"
                style={{ width: 140 }}
            >
                {/* Antenna */}
                <div className="flex flex-col items-center mb-1">
                    <div
                        className={`w-2.5 h-2.5 rounded-full ${(isActive || isOrchestrator) ? 'animate-pulse' : ''}`}
                        style={{ 
                            backgroundColor: (isActive || isOrchestrator) ? config.color : '#44403C',
                            opacity: (isActive || isOrchestrator) ? 1 : 0.3
                        }}
                    />
                    <div className="w-0.5 h-3 bg-stone-600" />
                </div>

                {/* Head/Face */}
                <div
                    className="rounded-2xl p-3 mb-1 transition-all duration-500"
                    style={{
                        backgroundColor: (isActive || isOrchestrator) ? '#1C1917' : '#0C0A09',
                        borderWidth: '2px',
                        borderStyle: 'solid',
                        borderColor: (isActive || isOrchestrator) ? config.color : '#292524',
                        boxShadow: (isActive || isOrchestrator) ? `0 0 12px ${config.color}50` : 'none',
                        width: 160,
                    }}
                >
                    {/* Eyes */}
                    <div className="flex justify-around mb-2">
                        {/* Left Eye */}
                        <div
                            className="w-5 h-5 rounded-full border-2 flex items-center justify-center transition-all duration-500"
                            style={{ 
                                borderColor: (isActive || isOrchestrator) ? config.eyeColor : '#292524',
                                backgroundColor: '#0C0A09',
                                boxShadow: (isActive || isOrchestrator) ? `0 0 8px ${config.eyeColor}` : 'none'
                            }}
                        >
                            <div
                                className={`w-2 h-2 rounded-full transition-all duration-500 ${(isActive || isOrchestrator) ? 'animate-pulse' : ''}`}
                                style={{ 
                                    backgroundColor: (isActive || isOrchestrator) ? config.eyeColor : '#1C1917',
                                    opacity: (isActive || isOrchestrator) ? 1 : 0.2
                                }}
                            />
                        </div>
                        {/* Right Eye */}
                        <div
                            className="w-5 h-5 rounded-full border-2 flex items-center justify-center transition-all duration-500"
                            style={{ 
                                borderColor: (isActive || isOrchestrator) ? config.eyeColor : '#292524',
                                backgroundColor: '#0C0A09',
                                boxShadow: (isActive || isOrchestrator) ? `0 0 8px ${config.eyeColor}` : 'none'
                            }}
                        >
                            <div
                                className={`w-2 h-2 rounded-full transition-all duration-500 ${(isActive || isOrchestrator) ? 'animate-pulse' : ''}`}
                                style={{ 
                                    backgroundColor: (isActive || isOrchestrator) ? config.eyeColor : '#1C1917',
                                    opacity: (isActive || isOrchestrator) ? 1 : 0.2
                                }}
                            />
                        </div>
                    </div>

                    {/* Agent Icon (Mouth/Badge Area) */}
                    <div
                        className="flex justify-center items-center py-1.5 rounded-lg mb-2 transition-all duration-500"
                        style={{ 
                            backgroundColor: (isActive || isOrchestrator) ? config.color + '30' : '#1C191730',
                            opacity: (isActive || isOrchestrator) ? 1 : 0.5
                        }}
                    >
                        <span style={{ color: (isActive || isOrchestrator) ? config.color : '#57534E' }}>{config.icon}</span>
                    </div>

                    {/* Agent Name */}
                    <div className="text-center">
                        <span 
                            className="text-[11px] font-bold uppercase tracking-wider transition-all duration-500"
                            style={{ color: (isActive || isOrchestrator) ? '#E7E5E4' : '#78716C' }}
                        >
                            {data.label}
                        </span>
                    </div>

                    {/* Token Stats Row */}
                    <div className="mt-2 flex items-center justify-between gap-1 px-1">
                        {/* Input Tokens */}
                        <div className="flex items-center gap-0.5">
                            <span className="text-[10px] text-blue-400">↑</span>
                            <span className="text-[10px] font-mono text-blue-300 font-semibold">
                                {data.inputTokens ? (data.inputTokens >= 1000 ? `${(data.inputTokens / 1000).toFixed(1)}K` : data.inputTokens) : '0'}
                            </span>
                        </div>

                        {/* Status Pill (Center) */}
                        {data.status && (
                            <span
                                className="text-[9px] px-2 py-0.5 rounded-full font-semibold uppercase tracking-wide transition-all duration-500"
                                style={{
                                    backgroundColor: (isActive || isOrchestrator) ? config.color + '40' : '#1C191740',
                                    color: (isActive || isOrchestrator) ? config.color : '#57534E',
                                    border: `1px solid ${(isActive || isOrchestrator) ? config.color : '#44403C'}`,
                                }}
                            >
                                {data.status}
                            </span>
                        )}

                        {/* Output Tokens */}
                        <div className="flex items-center gap-0.5">
                            <span className="text-[10px] text-green-400">↓</span>
                            <span className="text-[10px] font-mono text-green-300 font-semibold">
                                {data.outputTokens ? (data.outputTokens >= 1000 ? `${(data.outputTokens / 1000).toFixed(1)}K` : data.outputTokens) : '0'}
                            </span>
                        </div>
                    </div>

                    {/* Thought Signatures Row */}
                    {(data.thoughtSignatures !== undefined && data.thoughtSignatures !== null && data.thoughtSignatures > 0) && (
                        <div className="mt-1 flex items-center justify-center gap-0.5">
                            <FaLink className="text-purple-400" size={8} />
                            <span className="text-[10px] font-mono text-purple-300 font-semibold">
                                {data.thoughtSignatures}
                            </span>
                        </div>
                    )}

                    {/* Thought Stream (Last thought) */}
                    {data.thoughts && data.thoughts.length > 0 && (
                        <div className="mt-2 p-1.5 rounded bg-stone-900/50 border border-stone-800 max-w-[160px]">
                            <p className="text-[8px] text-stone-400 leading-tight truncate">
                                💭 {data.thoughts[0]}
                            </p>
                        </div>
                    )}

                    {/* Active Tool Badge */}
                    {data.activeTool && (
                        <div className="mt-1.5 flex items-center justify-center gap-1 text-[8px] text-amber-400">
                            <FaCog className="animate-spin" size={10} />
                            <span className="font-mono">{data.activeTool}</span>
                        </div>
                    )}

                    {/* Last Action Badge */}
                    {data.lastAction && (
                        <div className="mt-1.5 flex items-center justify-center gap-1 text-[8px] text-cyan-400">
                            <FaBolt className="text-cyan-400" size={10} />
                            <span className="font-mono">{data.lastAction}</span>
                        </div>
                    )}
                </div>

                {/* Neck/Base */}
                <div className="flex justify-center gap-2 mt-1">
                    <div 
                        className="w-3 h-1.5 rounded-sm transition-all duration-500" 
                        style={{ backgroundColor: (isActive || isOrchestrator) ? '#57534E' : '#292524' }}
                    />
                    <div 
                        className="w-3 h-1.5 rounded-sm transition-all duration-500"
                        style={{ backgroundColor: (isActive || isOrchestrator) ? '#57534E' : '#292524' }}
                    />
                </div>
            </div>
        </div>
    );
});

RichAgentNode.displayName = 'RichAgentNode';

export default RichAgentNode;
