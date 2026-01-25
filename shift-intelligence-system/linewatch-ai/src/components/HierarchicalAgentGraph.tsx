import React, { useEffect, useState, useRef } from 'react';
import ReactFlow, {
    Background,
    useNodesState,
    useEdgesState,
    MarkerType,
    ConnectionLineType,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { useStore } from '../store/useStore';
import RichAgentNode from './RichAgentNode';

import ThoughtBubbleNode from './ThoughtBubbleNode';

// Register custom node types OUTSIDE component to prevent warnings
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
    const [agentActions, setAgentActions] = useState<Record<string, {action: string, timestamp: number}>>({});
    
    // Support multiple active agents simultaneously
    const [activeAgents, setActiveAgents] = useState<Set<string>>(new Set());
    // Ref to track timeouts per agent to prevent closures from trapping stale state
    const activeTimersRef = useRef<Record<string, number>>({});
    
    const { agentStats, socket } = useStore();

    // Subscribe to agentStats for activation state
    useEffect(() => {
        // Extract active agents from store
        const activeSet = new Set<string>();
        Object.entries(agentStats || {}).forEach(([agentId, stats]) => {
            if (stats?.isActive) {
                activeSet.add(agentId);
            }
        });
        setActiveAgents(activeSet);
    }, [agentStats]);
    
    // Subscribe to agentStats for token tracking
    useEffect(() => {
        const tokens: Record<string, {input: number, output: number}> = {};
        Object.entries(agentStats || {}).forEach(([agentId, stats]) => {
            if (stats) {
                tokens[agentId] = {
                    input: stats.inputTokens || 0,
                    output: stats.outputTokens || 0
                };
            }
        });
        setAgentTokens(tokens);
    }, [agentStats]);
    
    // Subscribe to agentStats for action tracking
    useEffect(() => {
        const actions: Record<string, {action: string, timestamp: number}> = {};
        Object.entries(agentStats || {}).forEach(([agentId, stats]) => {
            if (stats?.lastAction) {
                actions[agentId] = {
                    action: stats.lastAction,
                    timestamp: stats.lastActionTime || Date.now()
                };
            }
        });
        setAgentActions(actions);
    }, [agentStats]);

    // Listen for agent_thinking WebSocket events (thought bubbles only)
    useEffect(() => {
        const handleMessage = (event: MessageEvent) => {
            try {
                const message = JSON.parse(event.data);

                // Handle thought bubbles ONLY
                if (message.type === 'agent_thinking') {
                    const { agent: rawAgent, thought } = message.data;
                    
                    // Edge case: validate agent exists
                    if (!rawAgent || !thought) return;
                    
                    const agent = rawAgent.toLowerCase();
                    // console.log('[HierarchicalAgentGraph] Received agent_thinking:', agent, thought?.substring(0, 50));

                    const bubbleId = `bubble-${Date.now()}-${Math.random()}`;
                    
                    // Add horizontal offset variation (-40 to +40 pixels)
                    const offsetX = (Math.random() - 0.5) * 80;

                    
                    // Auto-remove after 30 seconds (increased from 12s for better visibility)
                    const timeoutId = window.setTimeout(() => {
                        setThoughtBubbles(prev => {
                            const bubble = prev.find(b => b.id === bubbleId);
                            // Don't remove if it was dragged
                            if (bubble?.isDragged) return prev;
                            return prev.filter(b => b.id !== bubbleId);
                        });
                    }, 30000);
                    
                    setThoughtBubbles(prev => [...prev, {
                        id: bubbleId,
                        agentId: agent,
                        text: thought,
                        timestamp: Date.now(),
                        offsetX,
                        isDragged: false,
                        timeoutId,
                    }]);
                }
            } catch (e) {
                console.error('[HierarchicalAgentGraph] Failed to parse WebSocket message:', e);
            }
        };

        // Access the WebSocket from useStore (No global hacks)
        if (socket) {
            socket.addEventListener('message', handleMessage);
            return () => {
                socket.removeEventListener('message', handleMessage);
                // Clean up ALL timeouts on unmount
                Object.values(activeTimersRef.current).forEach(id => clearTimeout(id));
            };
        }
    }, [socket]);

    // Initialize nodes
    useEffect(() => {
        const labelMap: Record<string, string> = {
            orchestrator: 'Master Orchestrator',
            production: 'Production',
            compliance: 'Compliance',
            staffing: 'Staffing',
            maintenance: 'Maintenance',
        };

        const agentNodes = Object.keys(labelMap).map((key) => {
            const isActive = activeAgents.has(key);
            return {
                id: key,
                type: 'richAgent',
                position: POSITIONS[key as keyof typeof POSITIONS],
                data: {
                    agentId: key,
                    label: labelMap[key as keyof typeof labelMap],
                    type: key,
                    status: isActive ? 'Active' : (key === 'orchestrator' ? 'Coordination' : 'Ready'),
                    isActive: isActive,
                    inputTokens: agentTokens[key]?.input || 0,
                    outputTokens: agentTokens[key]?.output || 0,
                    lastAction: agentActions[key]?.action, // Pass the last action
                },
            };
        });

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
    }, [activeAgents, agentTokens, thoughtBubbles, agentActions]);

    // Initialize edges (Hub & Spoke from Orchestrator)
    useEffect(() => {
        const hubEdges = [
            { id: 'e-orch-prod', source: 'orchestrator', target: 'production' },
            { id: 'e-orch-comp', source: 'orchestrator', target: 'compliance' },
            { id: 'e-orch-staff', source: 'orchestrator', target: 'staffing' },
            { id: 'e-orch-maint', source: 'orchestrator', target: 'maintenance' },
        ].map((e) => {
            const isTargetActive = activeAgents.has(e.target);
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
    }, [activeAgents]);

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
