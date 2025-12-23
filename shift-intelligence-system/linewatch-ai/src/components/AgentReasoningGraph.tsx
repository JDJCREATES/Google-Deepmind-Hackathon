import React, { useEffect, useState } from 'react';
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
    const [activeAgent, setActiveAgent] = useState<string | null>(null);
    const [activeStep, setActiveStep] = useState<string | null>(null);
    const { logs } = useStore();
    
    useEffect(() => {
        fetchAndLayout();
    }, []);
    
    const fetchAndLayout = async () => {
        try {
            const res = await axios.get('http://localhost:8000/api/graph/structure');
            const { agents, agent_edges, hypothesis_nodes, hypothesis_edges } = res.data;
            
            const allNodes: any[] = [];
            const allEdges: any[] = [];
            
            // Layout constants - Orchestrator left, agents stacked vertically
            const orchestratorX = 100;
            const orchestratorY = 120; // Center vertically for 4 agents
            
            // Agent positions: stacked vertically to the right of orchestrator
            const agentX = 280;
            const agentStartY = 30;
            const agentSpacingY = 100; // Good vertical separation between rows
            
            const agentPositions = [
                { x: agentX, y: agentStartY },                      // Production Agent (top)
                { x: agentX, y: agentStartY + agentSpacingY },      // Compliance Agent
                { x: agentX, y: agentStartY + agentSpacingY * 2 },  // Staffing Agent
                { x: agentX, y: agentStartY + agentSpacingY * 3 },  // Maintenance Agent (bottom)
            ];
            
            const hypothesisStartX = 450; // Start hypothesis pipeline to the right of agents
            const hypothesisSpacingX = 95; // Horizontal spacing between hypothesis nodes
            
            // Add Orchestrator
            const orchestrator = agents.find((a: any) => a.type === 'orchestrator');
            if (orchestrator) {
                allNodes.push({
                    id: orchestrator.id,
                    type: 'default',
                    data: { label: orchestrator.label },
                    position: { x: orchestratorX, y: orchestratorY },
                    style: {
                        background: 'linear-gradient(135deg, #78350F 0%, #92400E 100%)',
                        color: '#fff',
                        border: '3px solid #F59E0B',
                        borderRadius: 10,
                        padding: '12px 20px',
                        fontSize: 12,
                        fontWeight: 800,
                        textAlign: 'center',
                        boxShadow: '0 6px 24px rgba(245, 158, 11, 0.35)',
                    },
                    sourcePosition: Position.Right,
                    targetPosition: Position.Left,
                });
            }
            
            // Add domain agents stacked vertically
            const domainAgents = agents.filter((a: any) => a.type === 'agent');
            domainAgents.forEach((agent: any, i: number) => {
                const pos = agentPositions[i] || { x: 20, y: 100 + i * 100 };
                
                // Agent node
                allNodes.push({
                    id: agent.id,
                    type: 'default',
                    data: { label: agent.label, nodeType: 'agent' },
                    position: pos,
                    style: {
                        background: '#1E40AF',
                        color: '#fff',
                        border: '2px solid #3B82F6',
                        borderRadius: 4,
                        padding: '6px 10px',
                        fontSize: 10,
                        fontWeight: 700,
                        minWidth: 130,
                        textAlign: 'center',
                    },
                    sourcePosition: Position.Right,
                    targetPosition: Position.Left,
                });
                
                // Orchestrator → Agent edge
                allEdges.push({
                    id: `orch_${agent.id}`,
                    source: 'orchestrator',
                    target: agent.id,
                    type: 'smoothstep',
                    style: { stroke: '#F59E0B', strokeWidth: 2 },
                    markerEnd: { type: MarkerType.ArrowClosed, color: '#F59E0B' },
                });
                
                // Add hypothesis nodes for this agent (HORIZONTAL pipeline - all same Y)
                hypothesis_nodes.forEach((hNode: any, j: number) => {
                    const nodeId = `${agent.id}_${hNode.id}`;
                    
                    allNodes.push({
                        id: nodeId,
                        type: 'default',
                        data: { label: hNode.label.split(' ').slice(1).join(' '), fullLabel: hNode.label, nodeType: hNode.type },
                        position: { x: hypothesisStartX + j * hypothesisSpacingX, y: pos.y }, // Same Y as agent - horizontal flow!
                        style: getHypothesisStyle(hNode.type),
                        sourcePosition: Position.Right,
                        targetPosition: Position.Left,
                    });
                });
                
                // Add hypothesis edges for this agent
                hypothesis_edges.forEach((hEdge: any) => {
                    const isLoop = hEdge.conditional === 'gather_more';
                    allEdges.push({
                        id: `${agent.id}_${hEdge.id}`,
                        source: `${agent.id}_${hEdge.source}`,
                        target: `${agent.id}_${hEdge.target}`,
                        type: 'smoothstep',
                        animated: false,
                        style: {
                            stroke: isLoop ? '#EAB308' : '#4B5563',
                            strokeWidth: isLoop ? 2 : 1,
                            strokeDasharray: isLoop ? '5,5' : undefined,
                        },
                        markerEnd: { type: MarkerType.ArrowClosed, color: isLoop ? '#EAB308' : '#4B5563', width: 12, height: 12 },
                        label: isLoop ? '⟲ retry' : undefined,
                        labelStyle: { fontSize: 8, fill: '#FCD34D', fontWeight: 600 },
                    });
                });
                
                // Edge from agent to first hypothesis step
                allEdges.push({
                    id: `${agent.id}_start`,
                    source: agent.id,
                    target: `${agent.id}_load_knowledge`,
                    type: 'smoothstep',
                    style: { stroke: '#3B82F6', strokeWidth: 1.5 },
                    markerEnd: { type: MarkerType.ArrowClosed, color: '#3B82F6' },
                });
            });
            
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
            setActiveAgent(agent);
            setActiveStep(step);
            
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
                setActiveAgent(null);
                setActiveStep(null);
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
