import React, { useEffect, useState, useCallback } from 'react';
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

const HierarchicalAgentGraph: React.FC = () => {
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);
    const [expandedAgents, setExpandedAgents] = useState<Set<string>>(new Set(['production_agent'])); // Start with one expanded
    const { logs } = useStore();
    
    // Fetch graph structure
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
    }, [expandedAgents]);
    
    const layoutGraph = (rawNodes: any[], rawEdges: any[]) => {
        // Separate top-level agents from nested reasoning nodes
        const topLevelNodes = rawNodes.filter((n: any) => n.level === 'top');
        const nestedNodes = rawNodes.filter((n: any) => n.level === 'nested');
        
        const layoutedNodes: any[] = [];
        const layoutedEdges: any[] = [];
        
        // Layout top-level agents horizontally
        const agentSpacing = 350;
        const agentY = 100;
        
        topLevelNodes.forEach((agent: any, index: number) => {
            const isExpanded = expandedAgents.has(agent.id);
            
            layoutedNodes.push({
                id: agent.id,
                type: 'default',
                data: {
                    label: (
                        <div onClick={() => toggleAgent(agent.id)} style={{ cursor: 'pointer' }}>
                            {agent.label}
                            <div style={{ fontSize: 9, marginTop: 4 }}>
                                {isExpanded ? '▼ Expanded' : '▶ Collapsed'}
                            </div>
                        </div>
                    )
                },
                position: { x: index * agentSpacing, y: agentY },
                style: getAgentStyle(agent.type, isExpanded),
                sourcePosition: Position.Bottom,
                targetPosition: Position.Top,
            });
            
            // If expanded, show nested reasoning nodes
            if (isExpanded && agent.id !== 'orchestrator') {
                const agentNested = nestedNodes.filter((n: any) => n.parent === agent.id);
                
                // Layout nested nodes in a vertical flow under the agent
                const nestedStartY = agentY + 120;
                const nestedSpacing = 100;
                
                agentNested.forEach((nested: any, nIndex: number) => {
                    layoutedNodes.push({
                        id: nested.id,
                        type: 'default',
                        data: { label: nested.label.split(' ').slice(1).join(' ') }, // Remove emoji for compactness
                        position: {
                            x: index * agentSpacing - 50,
                            y: nestedStartY + nIndex * nestedSpacing
                        },
                        style: getReasoningStyle(nested.type),
                        sourcePosition: Position.Bottom,
                        targetPosition: Position.Top,
                    });
                });
                
                // Add nested edges
                const agentEdges = rawEdges.filter((e: any) => e.parent === agent.id);
                agentEdges.forEach((edge: any) => {
                    layoutedEdges.push({
                        ...edge,
                        type: 'smoothstep',
                        animated: false,
                        style: { stroke: '#6B7280', strokeWidth: 1.5 },
                        markerEnd: { type: MarkerType.ArrowClosed, color: '#6B7280', width: 15, height: 15 },
                        label: edge.conditional,
                        labelStyle: { fontSize: 8, fill: '#9CA3AF' },
                    });
                });
            }
        });
        
        // Add top-level agent edges
        const topEdges = rawEdges.filter((e: any) => !e.parent);
        topEdges.forEach((edge: any) => {
            layoutedEdges.push({
                ...edge,
                type: 'smoothstep',
                animated: false,
                style: { stroke: '#F59E0B', strokeWidth: 3 },
                markerEnd: { type: MarkerType.ArrowClosed, color: '#F59E0B', width: 20, height: 20 },
            });
        });
        
        setNodes(layoutedNodes);
        setEdges(layoutedEdges);
    };
    
    const toggleAgent = (agentId: string) => {
        setExpandedAgents(prev => {
            const next = new Set(prev);
            if (next.has(agentId)) {
                next.delete(agentId);
            } else {
                next.add(agentId);
            }
            return next;
        });
    };
    
    const getAgentStyle = (type: string, expanded: boolean) => ({
        background: type === 'orchestrator' ? '#78350F' : '#1E40AF',
        color: '#fff',
        border: `3px solid ${type === 'orchestrator' ? '#F59E0B' : '#3B82F6'}`,
        borderRadius: 8,
        padding: 16,
        fontSize: 12,
        fontWeight: 700,
        minWidth: 200,
        textAlign: 'center' as const,
        boxShadow: expanded ? '0 4px 20px rgba(59, 130, 246, 0.4)' : 'none',
    });
    
    const getReasoningStyle = (type: string) => {
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
            borderRadius: 4,
            padding: 8,
            fontSize: 9,
            fontWeight: 600,
            minWidth: 140,
            textAlign: 'center' as const,
        };
    };
    
    // Real-time highlighting from logs
    useEffect(() => {
        if (logs.length === 0) return;
        
        const latestLog = logs[0].toLowerCase();
        
        // Detect which agent + reasoning step is active
        const agentMap: Record<string, string> = {
            'production': 'production_agent',
            'compliance': 'compliance_agent',
            'staffing': 'staffing_agent',
            'maintenance': 'maintenance_agent',
            'orchestrator': 'orchestrator',
        };
        
        const reasoningMap: Record<string, string> = {
            'knowledge': 'load_knowledge',
            'framework': 'classify_frameworks',
            'hypothesis': 'generate_hypotheses',
            'evidence': 'gather_evidence',
            'belief': 'update_beliefs',
            'action': 'select_action',
           'execute': 'execute_action',
            'validate': 'validate',
        };
        
        let activeAgent: string | null = null;
        let activeReasoning: string | null = null;
        
        for (const [keyword, agentId] of Object.entries(agentMap)) {
            if (latestLog.includes(keyword)) {
                activeAgent = agentId;
                break;
            }
        }
        
        for (const [keyword, reasoningId] of Object.entries(reasoningMap)) {
            if (latestLog.includes(keyword)) {
                activeReasoning = reasoningId;
                break;
            }
        }
        
        if (activeAgent || activeReasoning) {
            // Highlight nodes
            setNodes((nds) =>
                nds.map((node) => {
                    const isAgentActive = activeAgent === node.id;
                    const isReasoningActive = activeAgent && activeReasoning && 
                        node.id === `${activeAgent}_${activeReasoning}`;
                    
                    if (isAgentActive || isReasoningActive) {
                        return {
                            ...node,
                            style: {
                                ...node.style,
                                boxShadow: '0 0 25px 10px rgba(251, 191, 36, 0.9)',
                                border: '3px solid #FCD34D',
                                transform: 'scale(1.08)',
                            },
                        };
                    }
                    return node;
                })
            );
            
            // Reset after 2s
            setTimeout(() => {
                setNodes((nds) => nds.map((n) => ({ ...n, style: n.type === 'default' ? getAgentStyle(n.data.type, expandedAgents.has(n.id)) : n.style })));
            }, 2000);
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
                minZoom={0.3}
                maxZoom={1.2}
            >
                <Background color="#1F2937" gap={16} size={1} />
            </ReactFlow>
        </div>
    );
};

export default HierarchicalAgentGraph;
