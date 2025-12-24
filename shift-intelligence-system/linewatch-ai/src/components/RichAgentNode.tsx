import React, { memo } from 'react';
import { Handle, Position } from 'reactflow';
import { FaRobot, FaCog, FaHardHat, FaUserShield, FaUsers, FaWrench, FaIndustry, FaBrain } from 'react-icons/fa';
import { MdOutlineSmartToy } from 'react-icons/md';

interface RichAgentNodeProps {
    data: {
        agentId: string;
        label: string;
        type: 'orchestrator' | 'production' | 'compliance' | 'staffing' | 'maintenance';
        status?: string;
        thoughts?: string[];
        activeTool?: string;
        isActive?: boolean;
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

    return (
        <div
            className={`relative transition-all duration-300 ${isActive ? 'scale-105' : ''}`}
            style={{
                filter: isActive ? `drop-shadow(0 0 20px ${config.color})` : 'none',
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
                        className="w-2.5 h-2.5 rounded-full animate-pulse"
                        style={{ backgroundColor: config.color }}
                    />
                    <div className="w-0.5 h-3 bg-stone-600" />
                </div>

                {/* Head (Main Body) */}
                <div
                    className="relative rounded-2xl p-3 border-2"
                    style={{
                        backgroundColor: '#1C1917',
                        borderColor: config.color,
                        minWidth: 130,
                    }}
                >
                    {/* Eyes Row */}
                    <div className="flex justify-center gap-4 mb-2">
                        {/* Left Eye */}
                        <div
                            className="w-5 h-5 rounded-full border-2 flex items-center justify-center"
                            style={{ borderColor: config.eyeColor, backgroundColor: '#0C0A09' }}
                        >
                            <div
                                className={`w-2 h-2 rounded-full ${isActive ? 'animate-pulse' : ''}`}
                                style={{ backgroundColor: config.eyeColor }}
                            />
                        </div>
                        {/* Right Eye */}
                        <div
                            className="w-5 h-5 rounded-full border-2 flex items-center justify-center"
                            style={{ borderColor: config.eyeColor, backgroundColor: '#0C0A09' }}
                        >
                            <div
                                className={`w-2 h-2 rounded-full ${isActive ? 'animate-pulse' : ''}`}
                                style={{ backgroundColor: config.eyeColor }}
                            />
                        </div>
                    </div>

                    {/* Agent Icon (Mouth/Badge Area) */}
                    <div
                        className="flex justify-center items-center py-1.5 rounded-lg mb-2"
                        style={{ backgroundColor: config.color + '30' }}
                    >
                        <span style={{ color: config.color }}>{config.icon}</span>
                    </div>

                    {/* Agent Name */}
                    <div className="text-center">
                        <span className="text-[11px] font-bold text-stone-200 uppercase tracking-wider">
                            {data.label}
                        </span>
                    </div>

                    {/* Status Pill */}
                    {data.status && (
                        <div className="mt-2 flex justify-center">
                            <span
                                className="px-2 py-0.5 rounded-full text-[9px] font-semibold uppercase tracking-wide"
                                style={{
                                    backgroundColor: config.color + '40',
                                    color: config.color,
                                    border: `1px solid ${config.color}`,
                                }}
                            >
                                {data.status}
                            </span>
                        </div>
                    )}

                    {/* Thought Stream (Last thought) */}
                    {data.thoughts && data.thoughts.length > 0 && (
                        <div className="mt-2 p-1.5 rounded bg-stone-900/50 border border-stone-800">
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
                </div>

                {/* Neck/Base */}
                <div className="flex justify-center gap-2 mt-1">
                    <div className="w-3 h-1.5 rounded-sm bg-stone-700" />
                    <div className="w-3 h-1.5 rounded-sm bg-stone-700" />
                </div>
            </div>
        </div>
    );
});

RichAgentNode.displayName = 'RichAgentNode';

export default RichAgentNode;
