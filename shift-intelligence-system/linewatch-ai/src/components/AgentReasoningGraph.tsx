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
            
            // Layout constants - improved spacing
            const orchestratorX = 550;
            const orchestratorY = 20;
            const agentX = 20;
            const agentStartY = 100;
            const agentSpacingY = 140; // More vertical space between agent rows
            const hypothesisStartX = 180;
            const hypothesisSpacingX = 105; // More horizontal space between hypothesis nodes
            
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
                        padding: '14px 24px',
                        fontSize: 13,
                        fontWeight: 800,
                        textAlign: 'center',
                        boxShadow: '0 6px 24px rgba(245, 158, 11, 0.35)',
                    },
                    sourcePosition: Position.Bottom,
                    targetPosition: Position.Top,
                });
            }
            
            // Add domain agents (stacked vertically on left)
            const domainAgents = agents.filter((a: any) => a.type === 'agent');
            domainAgents.forEach((agent: any, i: number) => {
                const agentY = agentStartY + i * agentSpacingY;
                
                // Agent node
                allNodes.push({
                    id: agent.id,
                    type: 'default',
                    data: { label: agent.label, nodeType: 'agent' },
                    position: { x: agentX, y: agentY },
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
                    targetPosition: Position.Top,
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
                
                // Add hypothesis nodes for this agent (horizontal row)
                hypothesis_nodes.forEach((hNode: any, j: number) => {
                    const nodeId = `${agent.id}_${hNode.id}`;
                    allNodes.push({
                        id: nodeId,
                        type: 'default',
                        data: { label: hNode.label.split(' ').slice(1).join(' '), fullLabel: hNode.label, nodeType: hNode.type },
                        position: { x: hypothesisStartX + j * hypothesisSpacingX, y: agentY },
                        style: getHypothesisStyle(hNode.type),
                        sourcePosition: Position.Right,
                        targetPosition: Position.Left,
                    });
                });
                
                // Add hypothesis edges for this agent
                hypothesis_edges.forEach((hEdge: any) => {
                    allEdges.push({
                        id: `${agent.id}_${hEdge.id}`,
                        source: `${agent.id}_${hEdge.source}`,
                        target: `${agent.id}_${hEdge.target}`,
                        type: 'smoothstep',
                        animated: false,
                        style: {
                            stroke: hEdge.conditional === 'gather_more' ? '#EAB308' : '#4B5563',
                            strokeWidth: hEdge.conditional ? 1.5 : 1,
                            strokeDasharray: hEdge.conditional === 'gather_more' ? '4,4' : undefined,
                        },
                        markerEnd: { type: MarkerType.ArrowClosed, color: '#4B5563', width: 10, height: 10 },
                        label: hEdge.conditional === 'gather_more' ? '⟲' : undefined,
                        labelStyle: { fontSize: 9, fill: '#9CA3AF' },
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
