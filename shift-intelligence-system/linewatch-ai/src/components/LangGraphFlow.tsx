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

// Node positioning using Dagre layout algorithm (simplified)
const createLayoutedNodes = (nodes: any[], edges: any[]) => {
    // Simple hierarchical layout
    const nodesByLevel: Record<number, any[]> = {};
    const nodeLevel: Record<string, number> = {};
    
    // Calculate levels (simple BFS)
    const visited = new Set<string>();
    const queue: Array<{id: string, level: number}> = [];
    
    // Start with nodes that have no incoming edges
    const targetIds = new Set(edges.map((e: any) => e.target));
    const sourceIds = new Set(edges.map((e: any) => e.source));
    
    nodes.forEach((node: any) => {
        if (!targetIds.has(node.id)) {
            queue.push({id: node.id, level: 0});
        }
    });
    
    // BFS to assign levels
    while (queue.length > 0) {
        const {id,level} = queue.shift()!;
        if (visited.has(id)) continue;
        
        visited.add(id);
        nodeLevel[id] = level;
        
        if (!nodesByLevel[level]) nodesByLevel[level] = [];
        nodesByLevel[level].push(id);
        
        // Add children
        edges.forEach((edge: any) => {
            if (edge.source === id && !visited.has(edge.target)) {
                queue.push({id: edge.target, level: level + 1});
            }
        });
    }
    
    // Position nodes with better spacing
    const levelHeight = 150;
    const nodeWidth = 220;
    const horizontalSpacing = 80;
    
    const positioned = nodes.map((node: any) => {
        const level = nodeLevel[node.id] || 0;
        const nodesAtLevel = nodesByLevel[level] || [];
        const index = nodesAtLevel.indexOf(node.id);
        
        // Center the level horizontally
        const levelWidth = nodesAtLevel.length * (nodeWidth + horizontalSpacing);
        const startX = -levelWidth / 2 + 250; // Center around 250px
        
        return {
            id: node.id,
            type: 'default',
            data: { 
                label: node.label || node.id.replace(/_/g, ' ').toUpperCase()
            },
            position: {
                x: startX + index * (nodeWidth + horizontalSpacing),
                y: level * levelHeight + 50
            },
            style: {
                ...getNodeStyle(node.type || 'default'),
                width: nodeWidth,
            },
            sourcePosition: Position.Bottom,
            targetPosition: Position.Top,
        };
    });
    
    return positioned;
};

const getNodeStyle = (type: string) => {
    const baseStyle = {
        padding: 12,
        borderRadius: 6,
        fontSize: 11,
        fontWeight: 600,
        border: '2px solid',
        minWidth: 180,
        textAlign: 'center' as const,
    };
    
    const typeStyles: Record<string, any> = {
        hypothesis: {
            background: '#1E40AF',
            color: '#fff',
            borderColor: '#3B82F6',
        },
        evidence: {
            background: '#065F46',
            color: '#fff',
            borderColor: '#10B981',
        },
        belief: {
            background: '#7C2D12',
            color: '#fff',
            borderColor: '#EA580C',
        },
        action: {
            background: '#78350F',
            color: '#fff',
            borderColor: '#F59E0B',
        },
        execution: {
            background: '#831843',
            color: '#fff',
            borderColor: '#EC4899',
        },
        default: {
            background: '#1C1917',
            color: '#FCD34D',
            borderColor: '#78716C',
        },
    };
    
    return { ...baseStyle, ...(typeStyles[type] || typeStyles.default) };
};

const LangGraphFlow: React.FC = () => {
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);
    const [activeNode, setActiveNode] = useState<string | null>(null);
    const [activeEdges, setActiveEdges] = useState<Set<string>>(new Set());
    const { logs } = useStore();
    
    // Fetch graph structure on mount
    useEffect(() => {
        const fetchGraphStructure = async () => {
            try {
                const response = await axios.get('http://localhost:8000/api/graph/structure');
                const { nodes: rawNodes, edges: rawEdges } = response.data;
                
                // Layout nodes
                const layouted = createLayoutedNodes(rawNodes, rawEdges);
                setNodes(layouted);
                
                // Style edges
                const styledEdges = rawEdges.map((edge: any) => ({
                    ...edge,
                    type: 'smoothstep',
                    animated: false,
                    style: { stroke: '#6B7280', strokeWidth: 2 },
                    markerEnd: { type: MarkerType.ArrowClosed, color: '#6B7280' },
                    label: edge.conditional || undefined,
                    labelStyle: { fontSize: 9, fill: '#9CA3AF' },
                }));
                setEdges(styledEdges);
            } catch (error) {
                console.error('Failed to fetch graph structure:', error);
            }
        };
        
        fetchGraphStructure();
    }, []);
    
    // Listen for node activity from WebSocket
    useEffect(() => {
        if (logs.length === 0) return;
        
        const latestLog = logs[0].toLowerCase();
        
        // Map log messages to node IDs
        type NodeMapping = Record<string, string>;
        const nodeMap: NodeMapping = {
            'load_knowledge': 'load_knowledge',
            'loading knowledge': 'load_knowledge',
            'classify': 'classify_frameworks',
            'framework': 'classify_frameworks',
            'hypothesis': 'generate_hypotheses',
            'generating hypotheses': 'generate_hypotheses',
            'evidence': 'gather_evidence',
            'gathering evidence': 'gather_evidence',
            'belief': 'update_beliefs',
            'updating beliefs': 'update_beliefs',
            'select': 'select_action',
            'action': 'select_action',
            'execute': 'execute_action',
            'executing': 'execute_action',
            'counterfactual': 'counterfactual_replay',
            'drift': 'check_drift',
            'evolve': 'evolve_policy',
        };
        
        let detectedNode: string | null = null;
        for (const [keyword, nodeId] of Object.entries(nodeMap)) {
            if (latestLog.includes(keyword)) {
                detectedNode = nodeId;
                break;
            }
        }
        
        if (detectedNode) {
            setActiveNode(detectedNode);
            
            // Find edges connected to this node
            const relatedEdgeIds = edges
                .filter((e: any) => e.source === detectedNode || e.target === detectedNode)
                .map((e: any) => e.id);
            setActiveEdges(new Set(relatedEdgeIds));
            
            // Highlight node
            setNodes((nds: any[]) =>
                nds.map((node: any) => {
                    if (node.id === detectedNode) {
                        return {
                            ...node,
                            style: {
                                ...node.style,
                                boxShadow: '0 0 20px 8px rgba(251, 191, 36, 0.8)',
                                border: '3px solid #FCD34D',
                                transform: 'scale(1.05)',
                            },
                        };
                    }
                    return {
                        ...node,
                        style: {
                            ...getNodeStyle(node.type),
                        },
                    };
                })
            );
            
            // Animate edges
            setEdges((eds: any[]) =>
                eds.map((edge: any) => ({
                    ...edge,
                    animated: relatedEdgeIds.includes(edge.id),
                    style: {
                        ...edge.style,
                        stroke: relatedEdgeIds.includes(edge.id) ? '#FCD34D' : '#6B7280',
                        strokeWidth: relatedEdgeIds.includes(edge.id) ? 3 : 2,
                    },
                }))
            );
            
            // Reset after 2 seconds
            setTimeout(() => {
                setActiveNode(null);
                setActiveEdges(new Set());
                setNodes((nds: any[]) =>
                    nds.map((node: any) => ({
                        ...node,
                        style: getNodeStyle(node.type),
                    }))
                );
                setEdges((eds: any[]) =>
                    eds.map((edge: any) => ({
                        ...edge,
                        animated: false,
                        style: { stroke: '#6B7280', strokeWidth: 2 },
                    }))
                );
            }, 2000);
        }
    }, [logs, edges]);
    
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
                elementsSelectable={true}
                minZoom={0.5}
                maxZoom={1.5}
            >
                <Background color="#374151" gap={16} size={1} />
            </ReactFlow>
        </div>
    );
};

export default LangGraphFlow;
