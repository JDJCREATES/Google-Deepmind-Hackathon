import React, { useEffect, useMemo } from 'react';
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

// Register custom node types
const nodeTypes = {
    richAgent: RichAgentNode,
};

// Fixed positions for "Octopus" X-Layout
const POSITIONS = {
    orchestrator: { x: 0, y: 0 },
    production: { x: -320, y: -140 },
    compliance: { x: 320, y: -140 },
    staffing: { x: -240, y: 140 },
    maintenance: { x: 240, y: 140 },
};

const HierarchicalAgentGraph: React.FC = () => {
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);
    const { logs } = useStore();

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

    // Detect active agent from latest log
    const activeAgent = useMemo(() => {
        if (logs.length === 0) return null;
        const latest = logs[0];
        const source = (latest.source || '').toLowerCase();

        if (source.includes('orchestrator') || source.includes('master')) return 'orchestrator';
        if (source.includes('production')) return 'production';
        if (source.includes('compliance')) return 'compliance';
        if (source.includes('staffing')) return 'staffing';
        if (source.includes('maintenance')) return 'maintenance';
        return null;
    }, [logs]);

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
                },
            },
        ];

        setNodes(agentNodes);
    }, [agentThoughts, activeAgent]);

    // Initialize edges (Hub & Spoke from Orchestrator)
    useEffect(() => {
        const hubEdges = [
            { id: 'e-orch-prod', source: 'orchestrator', target: 'production' },
            { id: 'e-orch-comp', source: 'orchestrator', target: 'compliance' },
            { id: 'e-orch-staff', source: 'orchestrator', target: 'staffing' },
            { id: 'e-orch-maint', source: 'orchestrator', target: 'maintenance' },
        ].map((e) => ({
            ...e,
            type: 'smoothstep',
            animated: activeAgent !== null,
            style: { stroke: '#4B5563', strokeWidth: 2 },
            markerEnd: { type: MarkerType.ArrowClosed, color: '#4B5563', width: 16, height: 16 },
        }));

        setEdges(hubEdges);
    }, [activeAgent]);

    return (
        <div style={{ width: '100%', height: '100%' }}>
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
