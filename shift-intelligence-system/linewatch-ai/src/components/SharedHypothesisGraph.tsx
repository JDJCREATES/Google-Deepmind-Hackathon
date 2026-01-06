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

const SharedHypothesisGraph: React.FC = () => {
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);
    const [activeAgentStep, setActiveAgentStep] = useState<{agent: string, step: string} | null>(null);
    const { logs } = useStore();
    
    // Fetch and layout graph on mount
    useEffect(() => {
        const fetchAndLayout = async () => {
            try {
                const response = await axios.get('http://localhost:8000/api/graph/structure');
                const { nodes: rawNodes, edges: rawEdges } = response.data;
                
                const layoutedNodes: any[] = [];
                const layoutedEdges: any[] = [];
                
                // Layout constants
                const graphWidth = 900;
                const orchestratorY = 30;
                const agentsY = 120;
                const hypothesisY = 220;
                
                // Find node types
                const orchestrator = rawNodes.find((n: any) => n.type === 'orchestrator');
                const agents = rawNodes.filter((n: any) => n.type === 'agent');
                const hypothesisSteps = rawNodes.filter((n: any) => 
                    n.type === 'reasoning' || n.type === 'hypothesis' || 
                    n.type === 'evidence' || n.type === 'belief' || 
                    n.type === 'action' || n.type === 'execution'
                );
                
                // Position Orchestrator (centered top)
                if (orchestrator) {
                    layoutedNodes.push({
                        id: orchestrator.id,
                        type: 'default',
                        data: { label: orchestrator.label },
                        position: { x: graphWidth / 2 - 100, y: orchestratorY },
                        style: {
                            background: 'linear-gradient(135deg, #78350F 0%, #92400E 100%)',
                            color: '#fff',
                            border: '2px solid #F59E0B',
                            borderRadius: 8,
                            padding: '12px 20px',
                            fontSize: 12,
                            fontWeight: 700,
                            minWidth: 200,
                            textAlign: 'center',
                            boxShadow: '0 4px 20px rgba(245, 158, 11, 0.3)',
                        },
                        sourcePosition: Position.Bottom,
                        targetPosition: Position.Top,
                    });
                }
                
                // Position Agents (horizontal row)
                const agentSpacing = graphWidth / (agents.length + 1);
                agents.forEach((agent: any, i: number) => {
                    layoutedNodes.push({
                        id: agent.id,
                        type: 'default',
                        data: { label: agent.label, nodeType: 'agent' },
                        position: { x: agentSpacing * (i + 1) - 80, y: agentsY },
                        style: {
                            background: '#1E40AF',
                            color: '#fff',
                            border: '2px solid #3B82F6',
                            borderRadius: 6,
                            padding: '8px 14px',
                            fontSize: 11,
                            fontWeight: 600,
                            minWidth: 130,
                            textAlign: 'center',
                        },
                        sourcePosition: Position.Bottom,
                        targetPosition: Position.Top,
                    });
                });
                
                // Position Hypothesis Steps (HORIZONTAL row)
                const stepSpacing = graphWidth / (hypothesisSteps.length + 1);
                hypothesisSteps.forEach((step: any, i: number) => {
                    layoutedNodes.push({
                        id: step.id,
                        type: 'default',
                        data: { label: step.label, nodeType: step.type },
                        position: { x: stepSpacing * (i + 1) - 60, y: hypothesisY },
                        style: getStepStyle(step.type),
                        sourcePosition: Position.Right,
                        targetPosition: Position.Left,
                    });
                });
                
                // Layout edges
                rawEdges.forEach((edge: any) => {
                    const isLoop = edge.conditional === 'loop' || edge.type === 'loop';
                    
                    layoutedEdges.push({
                        id: edge.id,
                        source: edge.source,
                        target: edge.target,
                        type: 'smoothstep',
                        animated: false,
                        style: {
                            stroke: edge.type === 'static' ? '#F59E0B' : (isLoop ? '#EAB308' : '#4B5563'),
                            strokeWidth: edge.type === 'static' ? 2 : 1.5,
                            strokeDasharray: isLoop ? '4,4' : undefined,
                        },
                        markerEnd: {
                            type: MarkerType.ArrowClosed,
                            color: edge.type === 'static' ? '#F59E0B' : '#4B5563',
                            width: 12,
                            height: 12,
                        },
                        label: isLoop ? '⟲' : undefined,
                        labelStyle: { fontSize: 10, fill: '#9CA3AF' },
                    });
                });
                
                setNodes(layoutedNodes);
                setEdges(layoutedEdges);
            } catch (error) {
                console.error('Failed to fetch graph:', error);
            }
        };
        
        fetchAndLayout();
    }, []);
    
    const getStepStyle = (type: string) => {
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
            border: `2px solid ${c.border}`,
            borderRadius: 4,
            padding: '6px 10px',
            fontSize: 9,
            fontWeight: 600,
            minWidth: 90,
            textAlign: 'center' as const,
        };
    };
    
    // Real-time highlighting from reasoning traces
    const { reasoningTraces } = useStore();
    
    useEffect(() => {
        if (!reasoningTraces || reasoningTraces.length === 0) return;
        
        const latestTrace = reasoningTraces[reasoningTraces.length - 1];
        
        // Map agent names to node IDs
        const agentNodeId = latestTrace.agent.toLowerCase().replace('agent', '') + '_agent';
        
        // Map reasoning steps to hypothesis market nodes
        const stepMapping: Record<string, string> = {
            'reason': 'generate_hypotheses',
            'gather_evidence': 'gather_evidence',
            'update_beliefs': 'update_beliefs',
            'select_action': 'select_action',
            'execute': 'execute_action',
            'execute_action': 'execute_action',
        };
        
        const stepNodeId = stepMapping[latestTrace.step] || latestTrace.step;
        
        // Create dynamic edge from agent to step
        const dynamicEdgeId = `dynamic_${agentNodeId}_${stepNodeId}`;
        setEdges((eds) => {
            const filtered = eds.filter(e => !e.id.startsWith('dynamic_'));
            return [...filtered, {
                id: dynamicEdgeId,
                source: agentNodeId,
                target: stepNodeId,
                type: 'smoothstep',
                animated: true,
                style: { stroke: '#FCD34D', strokeWidth: 3 },
                markerEnd: { type: MarkerType.ArrowClosed, color: '#FCD34D' },
                label: `${(latestTrace.confidence * 100).toFixed(0)}%`,
                labelStyle: { fontSize: 10, fill: '#FCD34D', fontWeight: 'bold' },
            }];
        });
        
        // Highlight nodes
        setNodes((nds) => nds.map(n => {
            if (n.id === agentNodeId || n.id === stepNodeId) {
                return {
                    ...n,
                    style: {
                        ...n.style,
                        boxShadow: '0 0 20px 8px rgba(251, 191, 36, 0.7)',
                        border: '2px solid #FCD34D',
                    }
                };
            }
            return n;
        }));
        
        // Reset after 2.5s
        setTimeout(() => {
            setEdges((eds) => eds.filter(e => !e.id.startsWith('dynamic_')));
            setNodes((nds) => nds.map(n => ({
                ...n,
                style: n.data.nodeType === 'agent' 
                    ? { ...n.style, boxShadow: 'none', border: '2px solid #3B82F6' }
                    : { ...n.style, boxShadow: 'none' }
            })));
        }, 2500);
    }, [reasoningTraces]);
    
    return (
        <div style={{ width: '100%', height: '100%' }}>
            <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                fitView
                fitViewOptions={{ padding: 0.2 }}
                proOptions={{ hideAttribution: true }}
                nodesDraggable={true}
                nodesConnectable={false}
                minZoom={0.5}
                maxZoom={1.5}
            >
                <Background color="#1F2937" gap={20} size={1} />
            </ReactFlow>
        </div>
    );
};

export default SharedHypothesisGraph;
