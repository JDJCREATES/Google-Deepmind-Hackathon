import React, { useEffect, useMemo, useState, useRef } from 'react';
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

// Thought Bubble Node Component
const ThoughtBubbleNode: React.FC<{ data: { text: string; agentColor: string; isDragged: boolean; onClose: () => void; onDragStart: () => void } }> = ({ data }) => {
    return (
        <div 
            className="pointer-events-auto cursor-move"
            style={{
                animation: data.isDragged ? 'none' : 'thoughtDrift 12s ease-out forwards',
            }}
            onMouseDown={data.onDragStart}
        >
            <div 
                className="p-3 rounded-lg shadow-lg max-w-xs relative"
                style={{ 
                    backgroundColor: data.agentColor + '40', 
                    borderColor: data.agentColor, 
                    borderWidth: '1px', 
                    borderStyle: 'solid' 
                }}
            >
                {/* Close button */}
                <button
                    onClick={(e) => {
                        e.stopPropagation();
                        data.onClose();
                    }}
                    className="absolute -top-2 -right-2 w-5 h-5 rounded-full bg-stone-700 hover:bg-stone-600 text-stone-300 hover:text-white flex items-center justify-center text-xs font-bold transition-colors"
                    style={{ cursor: 'pointer' }}
                >
                    ×
                </button>
                <p className="text-xs text-stone-200 leading-tight font-medium">
                    {data.text}
                </p>
            </div>
            <style dangerouslySetInnerHTML={{__html: `
                @keyframes thoughtDrift {
                    0% {
                        transform: translateY(0);
                        opacity: 0;
                    }
                    10% {
                        opacity: 1;
                    }
                    90% {
                        opacity: 1;
                    }
                    100% {
                        transform: translateY(-180px);
                        opacity: 0;
                    }
                }
            `}} />
        </div>
    );
};

// Register custom node types
const nodeTypes = {
    richAgent: RichAgentNode,
    thoughtBubble: ThoughtBubbleNode,
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
    offsetX?: number;
    isDragged?: boolean;
    timeoutId?: number;
}

const HierarchicalAgentGraph: React.FC = () => {
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);
    const [thoughtBubbles, setThoughtBubbles] = useState<ThoughtBubbleData[]>([]);
    const [agentTokens, setAgentTokens] = useState<Record<string, {input: number, output: number}>>({});
    const [currentActiveAgent, setCurrentActiveAgent] = useState<string | null>(null);
    const activeAgentTimeoutRef = useRef<number | null>(null);
    const { logs, thoughtSignatures } = useStore();

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

    // Use currentActiveAgent from WebSocket events instead of logs
    const activeAgent = currentActiveAgent;

    // Listen for agent_thinking WebSocket events
    useEffect(() => {
        const handleMessage = (event: MessageEvent) => {
            try {
                const message = JSON.parse(event.data);

                
                // Handle thought bubbles
                if (message.type === 'agent_thinking') {
                    const { agent, thought } = message.data;

                    const bubbleId = `bubble-${Date.now()}-${Math.random()}`;
                    
                    // Add horizontal offset variation (-40 to +40 pixels)
                    const offsetX = (Math.random() - 0.5) * 80;

                    
                    // Auto-remove after 12 seconds
                    const timeoutId = window.setTimeout(() => {
                        setThoughtBubbles(prev => {
                            const bubble = prev.find(b => b.id === bubbleId);
                            // Don't remove if it was dragged
                            if (bubble?.isDragged) return prev;
                            return prev.filter(b => b.id !== bubbleId);
                        });
                    }, 12000);
                    
                    setThoughtBubbles(prev => [...prev, {
                        id: bubbleId,
                        agentId: agent,
                        text: thought,
                        timestamp: Date.now(),
                        offsetX,
                        isDragged: false,
                        timeoutId,
                    }]);
                    
                    // Clear any existing timeout
                    if (activeAgentTimeoutRef.current) {
                        clearTimeout(activeAgentTimeoutRef.current);
                    }
                    
                    // Set this agent as active
                    setCurrentActiveAgent(agent);

                    
                    // Auto-reset after 5 seconds (increased from 3)
                    activeAgentTimeoutRef.current = setTimeout(() => {

                        setCurrentActiveAgent(null);
                        activeAgentTimeoutRef.current = null;
                    }, 5000);
                }
                
                // Handle token stats
                if (message.type === 'agent_stats_update') {
                    const { agent, input_tokens, output_tokens } = message.data;

                    setAgentTokens(prev => {
                        const updated = {
                            ...prev,
                            [agent]: {
                                input: input_tokens,
                                output: output_tokens
                            }
                        };

                        return updated;
                    });
                }
            } catch (e) {
                console.error('[HierarchicalAgentGraph] Failed to parse WebSocket message:', e);
            }
        };

        // Access the WebSocket from useStore
        const ws = (window as any).__agentWebSocket;

        if (ws) {
            ws.addEventListener('message', handleMessage);
            return () => {
                ws.removeEventListener('message', handleMessage);
                // Clean up timeout on unmount
                if (activeAgentTimeoutRef.current) {
                    clearTimeout(activeAgentTimeoutRef.current);
                }
            };
        } else {

        }
    }, []);

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
                    thoughtSignatures: thoughtSignatures.orchestrator || 0,
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
                    thoughtSignatures: thoughtSignatures.production || 0,
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
                    thoughtSignatures: thoughtSignatures.compliance || 0,
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
                    thoughtSignatures: thoughtSignatures.staffing || 0,
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
                    thoughtSignatures: thoughtSignatures.maintenance || 0,
                },
            },
        ];

        // Add thought bubble nodes with vertical stacking
        const thoughtBubbleNodes = thoughtBubbles.map((bubble, index) => {
            const position = POSITIONS[bubble.agentId as keyof typeof POSITIONS];
            if (!position) return null;

            // Count how many bubbles for this agent came before this one
            const agentBubblesBefore = thoughtBubbles
                .slice(0, index)
                .filter(b => b.agentId === bubble.agentId).length;

            return {
                id: bubble.id,
                type: 'thoughtBubble',
                position: { 
                    x: position.x + 100 + (bubble.offsetX || 0), // Spawn to the right of agent node
                    y: position.y + 60 + (agentBubblesBefore * 60) // Spawn below agent node, stack downward
                },
                data: {
                    text: bubble.text,
                    agentColor: agentColors[bubble.agentId] || '#6B7280',
                    isDragged: bubble.isDragged || false,
                    onClose: () => {
                        setThoughtBubbles(prev => prev.filter(b => b.id !== bubble.id));
                        if (bubble.timeoutId) {
                            clearTimeout(bubble.timeoutId);
                        }
                    },
                    onDragStart: () => {
                        // Mark as dragged to prevent auto-removal
                        setThoughtBubbles(prev => prev.map(b => 
                            b.id === bubble.id ? { ...b, isDragged: true } : b
                        ));
                        if (bubble.timeoutId) {
                            clearTimeout(bubble.timeoutId);
                        }
                    },
                },
                draggable: true,
                selectable: true,
            };
        }).filter(Boolean) as any[];

        // Combine all nodes
        setNodes([...agentNodes, ...thoughtBubbleNodes]);
    }, [agentThoughts, activeAgent, agentTokens, thoughtBubbles, thoughtSignatures]);

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
