import React, { useEffect } from 'react';
import ReactFlow, {
    Background,
    useNodesState,
    useEdgesState,
    MarkerType,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { useStore } from '../store/useStore';

// Define types inline for reactflow v11
type NodeData = {
    label: string;
    status: string;
};

type FlowNode = {
    id: string;
    type: string;
    position: { x: number; y: number };
    data: NodeData;
    style?: any;
};

type FlowEdge = {
    id: string;
    source: string;
    target: string;
    animated?: boolean;
    style?: any;
    markerEnd?: any;
};

// Define the agent nodes in the hypothesis market graph
const initialNodes: FlowNode[] = [
    {
        id: 'orchestrator',
        type: 'default',
        position: { x: 250, y: 0 },
        data: { label: '🎯 ORCHESTRATOR', status: 'idle' },
        style: { background: '#1C1917', color: '#FCD34D', border: '2px solid #F59E0B', fontWeight: 'bold', fontSize: 11, borderRadius: 4 },
    },
    {
        id: 'production',
        type: 'default',
        position: { x: 50, y: 100 },
        data: { label: '🏭 Production', status: 'idle' },
        style: { background: '#334155', color: '#fff', border: '1px solid #475569', fontSize: 10, borderRadius: 4 },
    },
    {
        id: 'compliance',
        type: 'default',
        position: { x: 200, y: 100 },
        data: { label: '📋 Compliance', status: 'idle' },
        style: { background: '#334155', color: '#fff', border: '1px solid #475569', fontSize: 10, borderRadius: 4 },
    },
    {
        id: 'staffing',
        type: 'default',
        position: { x: 350, y: 100 },
        data: { label: '👷 Staffing', status: 'idle' },
        style: { background: '#334155', color: '#fff', border: '1px solid #475569', fontSize: 10, borderRadius: 4 },
    },
    {
        id: 'maintenance',
        type: 'default',
        position: { x: 500, y: 100 },
        data: { label: '🔧 Maintenance', status: 'idle' },
        style: { background: '#334155', color: '#fff', border: '1px solid #475569', fontSize: 10, borderRadius: 4 },
    },
    {
        id: 'hypothesis',
        type: 'default',
        position: { x: 250, y: 200 },
        data: { label: '🧪 Hypothesis Market', status: 'idle' },
        style: { background: '#1E40AF', color: '#fff', border: '2px solid #3B82F6', fontWeight: 'bold', fontSize: 10, borderRadius: 4 },
    },
    {
        id: 'action',
        type: 'default',
        position: { x: 250, y: 300 },
        data: { label: '⚡ Action Execution', status: 'idle' },
        style: { background: '#065F46', color: '#fff', border: '2px solid #10B981', fontWeight: 'bold', fontSize: 10, borderRadius: 4 },
    },
];

const initialEdges: FlowEdge[] = [
    { id: 'e-orch-prod', source: 'orchestrator', target: 'production', animated: false, style: { stroke: '#6B7280' } },
    { id: 'e-orch-comp', source: 'orchestrator', target: 'compliance', animated: false, style: { stroke: '#6B7280' } },
    { id: 'e-orch-staff', source: 'orchestrator', target: 'staffing', animated: false, style: { stroke: '#6B7280' } },
    { id: 'e-orch-maint', source: 'orchestrator', target: 'maintenance', animated: false, style: { stroke: '#6B7280' } },
    { id: 'e-agents-hypo', source: 'production', target: 'hypothesis', animated: false, style: { stroke: '#6B7280' } },
    { id: 'e-comp-hypo', source: 'compliance', target: 'hypothesis', animated: false, style: { stroke: '#6B7280' } },
    { id: 'e-staff-hypo', source: 'staffing', target: 'hypothesis', animated: false, style: { stroke: '#6B7280' } },
    { id: 'e-maint-hypo', source: 'maintenance', target: 'hypothesis', animated: false, style: { stroke: '#6B7280' } },
    { id: 'e-hypo-action', source: 'hypothesis', target: 'action', animated: false, style: { stroke: '#6B7280' }, markerEnd: { type: MarkerType.ArrowClosed } },
];

const AgentFlowGraph: React.FC = () => {
    const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
    const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
    const { logs } = useStore();

    // Listen for agent activity and animate nodes
    useEffect(() => {
        // Parse the latest log to determine which agent is active
        if (logs.length === 0) return;
        
        const latestLog = logs[0].toLowerCase();
        
        // Map log content to node IDs
        const agentMap: Record<string, string> = {
            'orchestrator': 'orchestrator',
            'production': 'production',
            'compliance': 'compliance',
            'staffing': 'staffing',
            'maintenance': 'maintenance',
            'hypothesis': 'hypothesis',
            'investigation': 'hypothesis',
        };
        
        let activeNodeId: string | null = null;
        for (const [keyword, nodeId] of Object.entries(agentMap)) {
            if (latestLog.includes(keyword)) {
                activeNodeId = nodeId;
                break;
            }
        }
        
        if (activeNodeId) {
            // Highlight the active node
            setNodes((nds) =>
                nds.map((node) => {
                    if (node.id === activeNodeId) {
                        return {
                            ...node,
                            style: {
                                ...node.style,
                                boxShadow: '0 0 15px 5px rgba(251, 191, 36, 0.6)',
                                border: '2px solid #FCD34D',
                            },
                        };
                    }
                    // Reset other nodes
                    return {
                        ...node,
                        style: {
                            ...node.style,
                            boxShadow: 'none',
                            border: node.id === 'orchestrator' ? '2px solid #F59E0B' : 
                                   node.id === 'hypothesis' ? '2px solid #3B82F6' :
                                   node.id === 'action' ? '2px solid #10B981' : '1px solid #475569',
                        },
                    };
                })
            );
            
            // Animate edges leading to active node
            setEdges((eds) =>
                eds.map((edge) => ({
                    ...edge,
                    animated: edge.target === activeNodeId || edge.source === activeNodeId,
                }))
            );
            
            // Reset after 2 seconds
            setTimeout(() => {
                setNodes((nds) =>
                    nds.map((node) => ({
                        ...node,
                        style: {
                            ...node.style,
                            boxShadow: 'none',
                        },
                    }))
                );
                setEdges((eds) =>
                    eds.map((edge) => ({
                        ...edge,
                        animated: false,
                    }))
                );
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
                nodesDraggable={false}
                nodesConnectable={false}
                elementsSelectable={false}
                panOnDrag={false}
                zoomOnScroll={false}
            >
                <Background color="#374151" gap={16} size={1} />
            </ReactFlow>
        </div>
    );
};

export default AgentFlowGraph;
