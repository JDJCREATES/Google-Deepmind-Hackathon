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
    const [activeAgentSteps, setActiveAgentSteps] = useState<Map<string, string>>(new Map());
    const { logs } = useStore();
    
    // Fetch and layout graph
    useEffect(() => {
        const fetchGraphStructure = async () => {
            try {
                const response = await axios.get('http://localhost:8000/api/graph/structure');
                const { nodes: rawNodes, edges: rawEdges } = response.data;
                
                layoutGraph(rawNodes, rawEdges);
            } catch (error) {
                console.error('Failed to fetch graph structure:', error);
            }
        };
        
        fetchGraphStructure();
    }, []);
    
    const layoutGraph = (rawNodes: any[], rawEdges: any[]) => {
        const layoutedNodes: any[] = [];
        
        // Layer positioning
        const orchestratorY = 50;
        const agentsY = 200;
        const hypothesisY = 400;
        
        const centerX = 400;
        const agentSpacing = 250;
        const hypothesisSpacing = 140;
        
        rawNodes.forEach((node: any) => {
            let position = { x: 0, y: 0 };
            let style = {};
            
            if (node.layer === 'top') {
                // Orchestrator at top center
                position = { x: centerX, y: orchestratorY };
                style = {
                    background: '#78350F',
                    color: '#fff',
                    border: '4px solid #F59E0B',
                    borderRadius: 10,
                    padding: 20,
                    fontSize: 14,
                    fontWeight: 800,
                    minWidth: 250,
                    textAlign: 'center' as const,
                    boxShadow: '0 8px 30px rgba(245, 158, 11, 0.4)',
                };
            } else if (node.layer === 'agents') {
                // 4 agents in a row
                const agentIndex = ['production_agent', 'compliance_agent', 'staffing_agent', 'maintenance_agent'].indexOf(node.id);
                const totalWidth = (4 - 1) * agentSpacing;
                const startX = centerX - totalWidth / 2;
                position = { x: startX + agentIndex * agentSpacing, y: agentsY };
                style = {
                    background: '#1E40AF',
                    color: '#fff',
                    border: '3px solid #3B82F6',
                    borderRadius: 8,
                    padding: 14,
                    fontSize: 12,
                    fontWeight: 700,
                    minWidth: 180,
                    textAlign: 'center' as const,
                };
            } else if (node.layer === 'hypothesis') {
                // Hypothesis pipeline at bottom in vertical line
                const hypothesisIndex = [
                    'load_knowledge', 'classify_frameworks', 'generate_hypotheses',
                    'gather_evidence', 'update_beliefs', 'select_action',
                    'execute_action', 'validate'
                ].indexOf(node.id);
                position = { x: centerX, y: hypothesisY + hypothesisIndex * hypothesisSpacing };
                style = getHypothesisStyle(node.type);
            }
            
            layoutedNodes.push({
                id: node.id,
                type: 'default',
                data: { label: node.label, nodeType: node.type, layer: node.layer },
                position,
                style,
                sourcePosition: Position.Bottom,
                targetPosition: Position.Top,
            });
        });
        
        // Layout static edges
        const layoutedEdges = rawEdges.map((edge: any) => {
            if (edge.type === 'static') {
                return {
                    ...edge,
                    type: 'smoothstep',
                    animated: false,
                    style: { stroke: '#F59E0B', strokeWidth: 3 },
                    markerEnd: { type: MarkerType.ArrowClosed, color: '#F59E0B' },
                };
            } else if (edge.type === 'pipeline') {
                return {
                    ...edge,
                    type: 'smoothstep',
                    animated: false,
                    style: {
                        stroke: edge.conditional === 'loop' ? '#EAB308' : '#6B7280',
                        strokeWidth: edge.conditional === 'loop' ? 2 : 2,
                        strokeDasharray: edge.conditional === 'loop' ? '5,5' : 'none',
                    },
                    markerEnd: { type: MarkerType.ArrowClosed, color: edge.conditional === 'loop' ? '#EAB308' : '#6B7280' },
                    label: edge.conditional === 'loop' ? '⟲ loop' : undefined,
                    labelStyle: { fontSize: 9, fill: '#9CA3AF' },
                };
            }
            return edge;
        });
        
        setNodes(layoutedNodes);
        setEdges(layoutedEdges);
    };
    
    const getHypothesisStyle = (type: string) => {
        const styles: Record<string, any> = {
            hypothesis: { background: '#1E40AF', borderColor: '#3B82F6' },
            evidence: { background: '#065F46', borderColor: '#10B981' },
            belief: { background: '#7C2D12', borderColor: '#EA580C' },
            action: { background: '#78350F', borderColor: '#F59E0B' },
            execution: { background: '#831843', borderColor: '#EC4899' },
            reasoning: { background: '#1C1917', borderColor: '#78716C' },
        };
        
        return {
            ...(styles[type] || styles.reasoning),
            color: '#fff',
            border: '2px solid',
            borderRadius: 6,
            padding: 10,
            fontSize: 10,
            fontWeight: 600,
            minWidth: 160,
            textAlign: 'center' as const,
        };
    };
    
    // Real-time tracking: which agent is working on which hypothesis step
    useEffect(() => {
        if (logs.length === 0) return;
        
        const latestLog = logs[0].toLowerCase();
        
        // Detect agent
        const agentMap: Record<string, string> = {
            'production': 'production_agent',
            'compliance': 'compliance_agent',
            'staffing': 'staffing_agent',
            'maintenance': 'maintenance_agent',
        };
        
        // Detect reasoning step
        const stepMap: Record<string, string> = {
            'knowledge': 'load_knowledge',
            'framework': 'classify_frameworks',
            'hypothesis': 'generate_hypotheses',
            'evidence': 'gather_evidence',
            'belief': 'update_beliefs',
            'select': 'select_action',
            'execute': 'execute_action',
            'validate': 'validate',
        };
        
        let detectedAgent: string  | null = null;
        let detectedStep: string | null = null;
        
        for (const [keyword, agentId] of Object.entries(agentMap)) {
            if (latestLog.includes(keyword)) {
                detectedAgent = agentId;
                break;
            }
        }
        
        for (const [keyword, stepId] of Object.entries(stepMap)) {
            if (latestLog.includes(keyword)) {
                detectedStep = stepId;
                break;
            }
        }
        
        if (detectedAgent && detectedStep) {
            // Update active agent-step mapping
            setActiveAgentSteps(prev => {
                const next = new Map(prev);
                next.set(detectedAgent, detectedStep);
                return next;
            });
            
            // Create dynamic edges from agent to hypothesis step
            setEdges(eds => {
                // Remove old dynamic edges
                const staticEdges = eds.filter(e => e.id.startsWith('h') || e.id.startsWith('orch'));
                
                // Add new dynamic edges for all active agent-step pairs
                const dynamicEdges: any[] = [];
                activeAgentSteps.forEach((step, agent) => {
                    dynamicEdges.push({
                        id: `dynamic_${agent}_${step}`,
                        source: agent,
                        target: step,
                        type: 'smoothstep',
                        animated: true,
                        style: { stroke: '#FCD34D', strokeWidth: 4 },
                        markerEnd: { type: MarkerType.ArrowClosed, color: '#FCD34D' },
                    });
                });
                
                // Always include current detection
                if (!activeAgentSteps.has(detectedAgent)) {
                    dynamicEdges.push({
                        id: `dynamic_${detectedAgent}_${detectedStep}`,
                        source: detectedAgent,
                        target: detectedStep,
                        type: 'smoothstep',
                        animated: true,
                        style: { stroke: '#FCD34D', strokeWidth: 4 },
                        markerEnd: { type: MarkerType.ArrowClosed, color: '#FCD34D' },
                    });
                }
                
                return [...staticEdges, ...dynamicEdges];
            });
            
            // Highlight nodes
            setNodes(nds =>
                nds.map(node => {
                    const isActiveAgent = node.id === detectedAgent;
                    const isActiveStep = node.id === detectedStep;
                    
                    if (isActiveAgent || isActiveStep) {
                        return {
                            ...node,
                            style: {
                                ...node.style,
                                boxShadow: '0 0 30px 12px rgba(251, 191, 36, 0.9)',
                                border: isActiveAgent ? '4px solid #FCD34D' : '3px solid #FCD34D',
                                transform: 'scale(1.1)',
                            },
                        };
                    }
                    return node;
                })
            );
            
            // Clear after 3 seconds
            setTimeout(() => {
                setActiveAgentSteps(prev => {
                    const next = new Map(prev);
                    next.delete(detectedAgent!);
                    return next;
                });
                
                setEdges(eds => eds.filter(e => !e.id.startsWith('dynamic')));
                setNodes(nds => nds.map(n => ({ ...n, style: n.data.layer === 'hypothesis' ? getHypothesisStyle(n.data.nodeType) : n.style })));
            }, 3000);
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
                proOptions={{ hideAttribution: true }}
                nodesDraggable={true}
                nodesConnectable={false}
                minZoom={0.4}
                maxZoom={1.3}
            >
                <Background color="#0F172A" gap={20} size={1} />
            </ReactFlow>
        </div>
    );
};

export default SharedHypothesisGraph;
