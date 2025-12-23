import React, { useEffect } from 'react';
import ReactFlow, {
    Background,
    useNodesState,
    useEdgesState,
    MarkerType,
    Position,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { useStore } from '../store/useStore';
import axios from 'axios';

/**
 * Agent Reasoning Graph
 * 
 * Layout:
 * - Top Center: Master Orchestrator
 * - Left Column: 4 Domain Agents stacked vertically
 * - Right of each agent: Their hypothesis pipeline (horizontal)
 */
const AgentReasoningGraph: React.FC = () => {
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);
    const { logs } = useStore();
    
    useEffect(() => {
        fetchAndLayout();
    }, []);
    
    const fetchAndLayout = async () => {
        try {
            const res = await axios.get('http://localhost:8000/api/graph/structure');
            const { agents, hypothesis_nodes, hypothesis_edges, reasoning_traces, thought_signatures } = res.data;
            
            const allNodes: any[] = [];
            const allEdges: any[] = [];
            
            // Layout Configuration
            const LANE_HEIGHT = 160; // Reduced from 200
            const AGENT_START_X = 100; // Moved left
            const STEP_START_X = 350;
            
            // Phase definitions for grouping (Much wider)
            const PHASES = [
                { id: 'Knowledge', x: STEP_START_X, width: 220, color: 'rgba(30, 58, 138, 0.15)' },
                { id: 'Hypothesis', x: STEP_START_X + 240, width: 220, color: 'rgba(6, 78, 59, 0.15)' },
                { id: 'Reasoning', x: STEP_START_X + 480, width: 650, color: 'rgba(124, 45, 18, 0.15)' }, // HUGE space for reasoning loop
                { id: 'Action', x: STEP_START_X + 1150, width: 300, color: 'rgba(120, 53, 15, 0.15)' }
            ];

            const domainAgents = agents.filter((a: any) => a.type === 'agent');
            const totalHeight = domainAgents.length * LANE_HEIGHT;
            const orchestratorY = totalHeight / 2 - 50;

            // 1. Add Background Phase Columns
            PHASES.forEach(phase => {
                allNodes.push({
                    id: `bg_phase_${phase.id}`,
                    type: 'default',
                    data: { label: phase.id.toUpperCase() },
                    position: { x: phase.x, y: -40 }, // Start higher for label visibility
                    style: {
                        width: phase.width - 20,
                        height: totalHeight + 60,
                        backgroundColor: phase.color,
                        border: 'none',
                        borderRadius: 12,
                        color: 'rgba(255,255,255,0.4)',
                        fontSize: 14,
                        fontWeight: 900,
                        letterSpacing: 2,
                        paddingTop: 15,
                        zIndex: -1,
                        pointerEvents: 'none',
                    },
                    selectable: false,
                    draggable: false,
                });
            });

            // 2. Add Orchestrator (Far Left)
            const orchestrator = agents.find((a: any) => a.type === 'orchestrator');
            if (orchestrator) {
                allNodes.push({
                    id: orchestrator.id,
                    type: 'default',
                    data: { label: "MASTER\nORCHESTRATOR" },
                    position: { x: -250, y: orchestratorY },
                    style: {
                        background: 'linear-gradient(135deg, #78350F 0%, #451a03 100%)',
                        color: '#FCD34D',
                        border: '3px solid #F59E0B',
                        borderRadius: 16,
                        padding: '20px',
                        fontSize: 16,
                        fontWeight: 800,
                        width: 180,
                        textAlign: 'center',
                        boxShadow: '0 8px 30px rgba(245, 158, 11, 0.3)',
                    },
                    sourcePosition: Position.Right,
                });
            }

            // 3. Add Agents and their Reasoning Lanes
            domainAgents.forEach((agent: any, i: number) => {
                const laneY = i * LANE_HEIGHT;
                const agentY = laneY + 60; // Center in lane
                
                // Agent Lane Background
                allNodes.push({
                    id: `lane_bg_${agent.id}`,
                    type: 'default',
                    data: { label: '' },
                    position: { x: AGENT_START_X - 20, y: laneY + 10 },
                    style: {
                        width: 1500, // Very wide to cover everything
                        height: LANE_HEIGHT - 20,
                        backgroundColor: 'rgba(17, 24, 39, 0.4)', 
                        border: '1px solid rgba(75, 85, 99, 0.4)',
                        borderRadius: 20,
                        zIndex: -2,
                        pointerEvents: 'none',
                    },
                    selectable: false
                });

                // Agent Node
                allNodes.push({
                    id: agent.id,
                    type: 'default',
                    data: { label: agent.label.replace(' Agent', '\nAgent') },
                    position: { x: AGENT_START_X, y: agentY },
                    style: {
                        background: '#1E3A8A',
                        color: '#BFDBFE',
                        border: '2px solid #3B82F6',
                        borderRadius: 12,
                        padding: '12px',
                        fontSize: 13,
                        fontWeight: 700,
                        width: 140,
                        textAlign: 'center',
                        boxShadow: '0 4px 15px rgba(59, 130, 246, 0.3)'
                    },
                    sourcePosition: Position.Right,
                    targetPosition: Position.Left,
                });

                // Orchestrator -> Agent Edge
                allEdges.push({
                    id: `orch_${agent.id}`,
                    source: 'orchestrator',
                    target: agent.id,
                    type: 'smoothstep',
                    style: { stroke: '#6B7280', strokeWidth: 2, strokeDasharray: '5,5' },
                    markerEnd: { type: MarkerType.ArrowClosed, color: '#6B7280' },
                });

                // Reasoning Steps (Pipeline)
                const phaseGroups: Record<string, any[]> = {
                    'Knowledge': [],
                    'Hypothesis': [],
                    'Reasoning': [],
                    'Action': []
                };

                hypothesis_nodes.forEach((n: any) => {
                    if (n.type === 'evidence') phaseGroups['Knowledge'].push(n);
                    else if (n.type === 'hypothesis') phaseGroups['Hypothesis'].push(n);
                    else if (n.type === 'action' || n.type === 'execution') phaseGroups['Action'].push(n);
                    else phaseGroups['Reasoning'].push(n);
                });

                hypothesis_nodes.forEach((hNode: any) => {
                    const stepId = `${agent.id}_${hNode.id}`;
                    
                    let phaseId = 'Reasoning';
                    if (hNode.type === 'evidence') phaseId = 'Knowledge';
                    else if (hNode.type === 'hypothesis') phaseId = 'Hypothesis';
                    else if (hNode.type === 'action' || hNode.type === 'execution') phaseId = 'Action';

                    const phaseDef = PHASES.find(p => p.id === phaseId) || PHASES[2];
                    
                    // Fixed spacing within phase
                    const indexInPhase = phaseGroups[phaseId].findIndex(n => n.id === hNode.id);
                    // Use generous fixed spacing
                    const nodeWidth = 120;
                    const spacing = 40;
                    const offsetX = indexInPhase * (nodeWidth + spacing);
                    
                    // Center group in phase area roughly, or just start from left padding
                    const finalX = phaseDef.x + 30 + offsetX;

                    allNodes.push({
                        id: stepId,
                        type: 'default',
                        data: { label: hNode.label.split(' ').slice(1).join(' ') },
                        position: { x: finalX, y: agentY },
                        style: {
                            ...getHypothesisStyle(hNode.type),
                            width: nodeWidth, // Hardcode width
                            fontSize: 11, // Larger font
                            padding: '8px', 
                        },
                        sourcePosition: Position.Right,
                        targetPosition: Position.Left,
                    });
                });

                // Reasoning Edges
                hypothesis_edges.forEach((hEdge: any) => {
                    const isLoop = hEdge.conditional === 'gather_more';
                    const sourceId = `${agent.id}_${hEdge.source}`;
                    const targetId = `${agent.id}_${hEdge.target}`;
                    
                    allEdges.push({
                        id: `${agent.id}_${hEdge.id}`,
                        source: sourceId,
                        target: targetId,
                        type: isLoop ? 'default' : 'smoothstep', // Bezier for loops
                        animated: false,
                        style: {
                            stroke: isLoop ? '#F59E0B' : '#4B5563',
                            strokeWidth: isLoop ? 2 : 1,
                            opacity: 0.6
                        },
                        markerEnd: { type: MarkerType.ArrowClosed, color: isLoop ? '#F59E0B' : '#4B5563', width: 6, height: 6 },
                    });
                });

                // Agent -> Start Edge
                allEdges.push({
                    id: `${agent.id}_start`,
                    source: agent.id,
                    target: `${agent.id}_load_knowledge`,
                    type: 'smoothstep',
                    style: { stroke: '#3B82F6', strokeWidth: 1.5, opacity: 0.8 },
                });
            });
            
            // 4. Add Live Reasoning Traces (Thought Bubbles)
            if (reasoning_traces && reasoning_traces.length > 0) {
                const agentTraceCount: Record<string, number> = {};
                
                reasoning_traces.forEach((trace: any, i: number) => {
                    const agentId = trace.agent?.toLowerCase().replace('agent', '_agent') || 'production_agent';
                    agentTraceCount[agentId] = (agentTraceCount[agentId] || 0) + 1;
                    
                    // Find agent's lane Y position
                    const agentIndex = domainAgents.findIndex((a: any) => a.id === agentId);
                    const laneY = agentIndex >= 0 ? agentIndex * LANE_HEIGHT : 0;
                    
                    // Position traces to the far right of the lane
                    const traceX = STEP_START_X + 1500 + (agentTraceCount[agentId] * 150);
                    const traceY = laneY + 60;
                    
                    allNodes.push({
                        id: `trace_${trace.id || i}`,
                        type: 'default',
                        data: { 
                            label: `💭 ${trace.thought?.substring(0, 40) || 'Thinking...'}${trace.thought?.length > 40 ? '...' : ''}`,
                        },
                        position: { x: traceX, y: traceY },
                        style: {
                            background: 'linear-gradient(135deg, #6366F1 0%, #4F46E5 100%)',
                            color: '#E0E7FF',
                            border: '2px solid #818CF8',
                            borderRadius: 16,
                            padding: '10px',
                            fontSize: 10,
                            fontStyle: 'italic',
                            width: 140,
                            boxShadow: '0 4px 15px rgba(99, 102, 241, 0.4)',
                            animation: 'pulse 2s infinite',
                        },
                        sourcePosition: Position.Left,
                        targetPosition: Position.Right,
                    });
                    
                    // Connect trace to the agent
                    if (agentIndex >= 0) {
                        allEdges.push({
                            id: `trace_edge_${trace.id || i}`,
                            source: agentId,
                            target: `trace_${trace.id || i}`,
                            type: 'smoothstep',
                            animated: true,
                            style: { stroke: '#818CF8', strokeWidth: 1, strokeDasharray: '3,3' },
                        });
                    }
                });
            }
            
            // 5. Add Thought Signature Indicator (if any)
            if (thought_signatures && thought_signatures.length > 0) {
                const latestSig = thought_signatures[thought_signatures.length - 1];
                allNodes.push({
                    id: 'thought_sig_indicator',
                    type: 'default',
                    data: { label: `🔐 Sig: ${latestSig.hash?.substring(0, 8) || 'N/A'}` },
                    position: { x: -250, y: -60 },
                    style: {
                        background: '#1F2937',
                        color: '#9CA3AF',
                        border: '1px solid #374151',
                        borderRadius: 8,
                        padding: '6px',
                        fontSize: 9,
                        fontFamily: 'monospace',
                    },
                    selectable: false,
                });
            }
            
            setNodes(allNodes);
            setEdges(allEdges);
        } catch (err) {
            console.error('Graph fetch error:', err);
        }
    };
    
    const getHypothesisStyle = (type: string) => {
        const colors: Record<string, {bg: string, border: string}> = {
            hypothesis: { bg: '#1E3A8A', border: '#3B82F6' },
            evidence: { bg: '#064E3B', border: '#10B981' },
            belief: { bg: '#7C2D12', border: '#EA580C' },
            action: { bg: '#78350F', border: '#F59E0B' },
            execution: { bg: '#831843', border: '#EC4899' },
            reasoning: { bg: '#1C1917', border: '#57534E' },
        };
        const c = colors[type] || colors.reasoning;
        return {
            background: c.bg,
            color: '#fff',
            border: `1.5px solid ${c.border}`,
            borderRadius: 3,
            padding: '4px 6px',
            fontSize: 7,
            fontWeight: 600,
            minWidth: 60,
            maxWidth: 80,
            textAlign: 'center' as const,
        };
    };
    
    // Real-time highlighting
    useEffect(() => {
        if (logs.length === 0) return;
        const log = logs[0].toLowerCase();
        
        const agentMap: Record<string, string> = {
            production: 'production_agent',
            compliance: 'compliance_agent',
            staffing: 'staffing_agent',
            maintenance: 'maintenance_agent',
        };
        const stepMap: Record<string, string> = {
            knowledge: 'load_knowledge',
            framework: 'classify_frameworks',
            hypothesis: 'generate_hypotheses',
            evidence: 'gather_evidence',
            belief: 'update_beliefs',
            select: 'select_action',
            execute: 'execute_action',
            counterfactual: 'counterfactual_replay',
            drift: 'check_drift',
            evolve: 'evolve_policy',
        };
        
        let agent: string | null = null;
        let step: string | null = null;
        for (const [kw, id] of Object.entries(agentMap)) {
            if (log.includes(kw)) { agent = id; break; }
        }
        for (const [kw, id] of Object.entries(stepMap)) {
            if (log.includes(kw)) { step = id; break; }
        }
        
        if (agent && step) {
            const targetNodeId = `${agent}_${step}`;
            
            // Add dynamic edge
            setEdges(eds => {
                const filtered = eds.filter(e => !e.id.startsWith('dynamic_'));
                return [...filtered, {
                    id: `dynamic_${agent}_${step}`,
                    source: agent!,
                    target: targetNodeId,
                    type: 'smoothstep',
                    animated: true,
                    style: { stroke: '#FCD34D', strokeWidth: 3 },
                    markerEnd: { type: MarkerType.ArrowClosed, color: '#FCD34D' },
                }];
            });
            
            // Highlight nodes
            setNodes(nds => nds.map(n => {
                if (n.id === agent || n.id === targetNodeId) {
                    return {
                        ...n,
                        style: {
                            ...n.style,
                            boxShadow: '0 0 20px 8px rgba(251, 191, 36, 0.8)',
                            border: '2px solid #FCD34D',
                        },
                    };
                }
                return n;
            }));
            
            setTimeout(() => {
                setEdges(eds => eds.filter(e => !e.id.startsWith('dynamic_')));
                fetchAndLayout(); // Reset styles
            }, 2500);
        }
    }, [logs]);
    
    return (
        <div style={{ width: '100%', height: '100%' }}>
            <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                fitView
                fitViewOptions={{ padding: 0.15 }}
                proOptions={{ hideAttribution: true }}
                nodesDraggable={true}
                nodesConnectable={false}
                minZoom={0.4}
                maxZoom={1.4}
            >
                <Background color="#1F2937" gap={16} size={1} />
            </ReactFlow>
        </div>
    );
};

export default AgentReasoningGraph;
