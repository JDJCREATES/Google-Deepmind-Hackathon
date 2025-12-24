import React, { useEffect, useMemo, useState } from 'react';
import ReactFlow, {
    Background,
    useNodesState,
    useEdgesState,
    MarkerType,
    ConnectionLineType,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { useStore, type LogEntry } from '../store/useStore';
import RichAgentNode from './RichAgentNode';
import ThoughtBubble from './ThoughtBubble';

// Register custom node types
const nodeTypes = {
    richAgent: RichAgentNode,
};

// Fixed positions for "Octopus" X-Layout
const POSITIONS = {
    orchestrator: { x: 0, y: 0 },
    production: { x: -320, y: -140 },
    compliance: { x: 320, y: -140 },
    staffing: { x: -240, y: 140 },
    maintenance: { x: 240, y: 140 },
};

const agentColors: Record<string, string> = {
    orchestrator: '#F59E0B',
    production: '#3B82F6',
    compliance: '#10B981',
    staffing: '#8B5CF6',
    maintenance: '#EF4444',
};

interface ThoughtBubbleData {
    id: string;
    agentId: string;
    text: string;
    timestamp: number;
}

const HierarchicalAgentGraph: React.FC = () => {
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);
    const [thoughtBubbles, setThoughtBubbles] = useState<ThoughtBubbleData[]>([]);
    const [agentTokens, setAgentTokens] = useState<Record<string, {input: number, output: number}>>({});
    const { logs } = useStore();

    // Extract agent-specific logs for thought streams
    const agentThoughts = useMemo(() => {
        const thoughts: Record<string, string[]> = {
            orchestrator: [],
            production: [],
            compliance: [],
            staffing: [],
            maintenance: [],
        };

        logs.forEach((log: LogEntry) => {
            const source = (log.source || '').toLowerCase();
            const desc = log.description || log.type;

            if (source.includes('orchestrator') || source.includes('master')) {
                thoughts.orchestrator.push(desc);
            } else if (source.includes('production')) {
                thoughts.production.push(desc);
            } else if (source.includes('compliance')) {
                thoughts.compliance.push(desc);
            } else if (source.includes('staffing')) {
                thoughts.staffing.push(desc);
            } else if (source.includes('maintenance')) {
                thoughts.maintenance.push(desc);
            }
        });

        // Keep only the 3 most recent per agent
        Object.keys(thoughts).forEach((key) => {
            thoughts[key] = thoughts[key].slice(0, 3);
        });

        return thoughts;
    }, [logs]);

    // Detect active agent from latest log
    const activeAgent = useMemo(() => {
        if (logs.length === 0) return null;
        const latest = logs[0];
        const source = (latest.source || '').toLowerCase();

        if (source.includes('orchestrator') || source.includes('master')) return 'orchestrator';
        if (source.includes('production')) return 'production';
        if (source.includes('compliance')) return 'compliance';
        if (source.includes('staffing')) return 'staffing';
        if (source.includes('maintenance')) return 'maintenance';
        return null;
    }, [logs]);

    // Listen for agent_thinking WebSocket events
    useEffect(() => {
        const handleMessage = (event: MessageEvent) => {
            try {
                const message = JSON.parse(event.data);
                
                // Handle thought bubbles
                if (message.type === 'agent_thinking') {
                    const { agent, thought } = message.data;
                    const bubbleId = `bubble-${Date.now()}-${Math.random()}`;
                    
                    setThoughtBubbles(prev => [...prev, {
                        id: bubbleId,
                        agentId: agent,
                        text: thought,
                        timestamp: Date.now()
                    }]);
                }
                
                // Handle token stats
                if (message.type === 'agent_stats_update') {
                    const { agent, input_tokens, output_tokens } = message.data;
                    setAgentTokens(prev => ({
                        ...prev,
                        [agent]: {
                            input: input_tokens,
                            output: output_tokens
                        }
                    }));
                }
            } catch (e) {
                // Ignore parse errors
            }
        };

        // Access the WebSocket from useStore
        const ws = (window as any).__agentWebSocket;
        if (ws) {
            ws.addEventListener('message', handleMessage);
            return () => ws.removeEventListener('message', handleMessage);
        }
    }, []);

    const removeBubble = (id: string) => {
        setThoughtBubbles(prev => prev.filter(b => b.id !== id));
    };

    // Initialize nodes
    useEffect(() => {
        const agentNodes = [
            {
                id: 'orchestrator',
                type: 'richAgent',
                position: POSITIONS.orchestrator,
                data: {
                    agentId: 'orchestrator',
                    label: 'Master Orchestrator',
                    type: 'orchestrator',
                    status: activeAgent === 'orchestrator' ? 'Deliberating' : 'Idle',
                    thoughts: agentThoughts.orchestrator,
                    isActive: activeAgent === 'orchestrator',
                    inputTokens: agentTokens.orchestrator?.input || 0,
                    outputTokens: agentTokens.orchestrator?.output || 0,
                },
            },
            {
                id: 'production',
                type: 'richAgent',
                position: POSITIONS.production,
                data: {
                    agentId: 'production',
                    label: 'Production',
                    type: 'production',
                    status: activeAgent === 'production' ? 'Analyzing' : 'Ready',
                    thoughts: agentThoughts.production,
                    isActive: activeAgent === 'production',
                    inputTokens: agentTokens.production?.input || 0,
                    outputTokens: agentTokens.production?.output || 0,
                },
            },
            {
                id: 'compliance',
                type: 'richAgent',
                position: POSITIONS.compliance,
                data: {
                    agentId: 'compliance',
                    label: 'Compliance',
                    type: 'compliance',
                    status: activeAgent === 'compliance' ? 'Checking' : 'Ready',
                    thoughts: agentThoughts.compliance,
                    isActive: activeAgent === 'compliance',
                    inputTokens: agentTokens.compliance?.input || 0,
                    outputTokens: agentTokens.compliance?.output || 0,
                },
            },
            {
                id: 'staffing',
                type: 'richAgent',
                position: POSITIONS.staffing,
                data: {
                    agentId: 'staffing',
                    label: 'Staffing',
                    type: 'staffing',
                    status: activeAgent === 'staffing' ? 'Scheduling' : 'Ready',
                    thoughts: agentThoughts.staffing,
                    isActive: activeAgent === 'staffing',
                    inputTokens: agentTokens.staffing?.input || 0,
                    outputTokens: agentTokens.staffing?.output || 0,
                },
            },
            {
                id: 'maintenance',
                type: 'richAgent',
                position: POSITIONS.maintenance,
                data: {
                    agentId: 'maintenance',
                    label: 'Maintenance',
                    type: 'maintenance',
                    status: activeAgent === 'maintenance' ? 'Inspecting' : 'Ready',
                    thoughts: agentThoughts.maintenance,
                    isActive: activeAgent === 'maintenance',
                    inputTokens: agentTokens.maintenance?.input || 0,
                    outputTokens: agentTokens.maintenance?.output || 0,
                },
            },
        ];

        setNodes(agentNodes);
    }, [agentThoughts, activeAgent, agentTokens]);

    // Initialize edges (Hub & Spoke from Orchestrator)
    useEffect(() => {
        const hubEdges = [
            { id: 'e-orch-prod', source: 'orchestrator', target: 'production' },
            { id: 'e-orch-comp', source: 'orchestrator', target: 'compliance' },
            { id: 'e-orch-staff', source: 'orchestrator', target: 'staffing' },
            { id: 'e-orch-maint', source: 'orchestrator', target: 'maintenance' },
        ].map((e) => {
            const isTargetActive = activeAgent === e.target;
            return {
                ...e,
                type: 'smoothstep',
                animated: isTargetActive,
                style: { 
                    stroke: isTargetActive ? '#F59E0B' : '#374151', 
                    strokeWidth: isTargetActive ? 3 : 2,
                    opacity: isTargetActive ? 1 : 0.3,
                },
                markerEnd: { 
                    type: MarkerType.ArrowClosed, 
                    color: isTargetActive ? '#F59E0B' : '#374151', 
                    width: isTargetActive ? 18 : 14, 
                    height: isTargetActive ? 18 : 14 
                },
            };
        });

        setEdges(hubEdges);
    }, [activeAgent]);

    return (
        <div style={{ width: '100%', height: '100%', position: 'relative' }}>
            {/* Thought Bubbles Layer */}
            {thoughtBubbles.map((bubble) => {
                const position = POSITIONS[bubble.agentId as keyof typeof POSITIONS];
                if (!position) return null;

                return (
                    <div
                        key={bubble.id}
                        style={{
                            position: 'absolute',
                            left: `calc(50% + ${position.x}px)`,
                            top: `calc(50% + ${position.y - 80}px)`,
                            transform: 'translate(-50%, -50%)',
                            zIndex: 1000,
                        }}
                    >
                        <ThoughtBubble
                            id={bubble.id}
                            text={bubble.text}
                            agentColor={agentColors[bubble.agentId] || '#6B7280'}
                            onComplete={removeBubble}
                        />
                    </div>
                );
            })}

            <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                nodeTypes={nodeTypes}
                fitView
                fitViewOptions={{ padding: 0.15, minZoom: 0.7, maxZoom: 1.2 }}
                proOptions={{ hideAttribution: true }}
                nodesDraggable={true}
                nodesConnectable={false}
                minZoom={0.5}
                maxZoom={1.5}
                defaultViewport={{ x: 0, y: 0, zoom: 0.85 }}
                connectionLineType={ConnectionLineType.SmoothStep}
            >
                <Background color="#1F2937" gap={24} size={1} />
            </ReactFlow>
        </div>
    );
};

export default HierarchicalAgentGraph;
