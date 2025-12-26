import React, { useEffect, useLayoutEffect, useState, useRef } from 'react';
import { Stage, Layer, Rect, Text, Group, Circle } from 'react-konva';
import Konva from 'konva';
import { useStore, type ConveyorBox, type WarehouseInventory } from '../store/useStore';

import MachineStack from './map/MachineStack';
import OperatorComp from './map/OperatorComp';
import ConveyorComp from './map/ConveyorComp';
import CameraComp from './map/CameraComp';
import MaintenanceCrewComp from './map/MaintenanceCrewComp';

// =============================================================================
// THEME & CONSTANTS
// =============================================================================

const THEME = {
    bg: '#0F172A',
    grid: '#1E293B',
    floor: '#1E293B',
    wall: '#334155',
    zones: {
        walkable: 'rgba(30, 41, 59, 0.5)',
        restricted: 'rgba(239, 68, 68, 0.1)',
        warehouse: 'rgba(59, 130, 246, 0.1)',
        breakroom: 'rgba(16, 185, 129, 0.05)',
        maintenance: 'rgba(249, 115, 22, 0.05)', 
    },
    // Restored keys
    machine: {
        body: '#0EA5E9',
        equipment: '#0D9488',
        connector: '#475569',
    },
    conveyor: {
        belt: '#64748B',
        running: '#10B981',
        stopped: '#EF4444',
    },
    operator: {
        active: '#22C55E',
        idle: '#F59E0B',
        moving: '#0EA5E9',
        inspecting: '#10B981',
    },
    camera: {
        body: '#1E293B',
        cone: '#FCD34D',
        active: '#22C55E',
    },
    status: {
        ok: '#10B981',
        warning: '#F59E0B',
        critical: '#EF4444',
    }
};

const PRODUCT_COLORS: Record<string, string> = {
    widget_a: '#3B82F6',
    widget_b: '#10B981',
    gizmo_x: '#F59E0B',
    gizmo_y: '#818CF8', // Indigo
    part_z: '#8B5CF6',
};

// =============================================================================
// MAIN COMPONENT
// =============================================================================

const FloorMap: React.FC = () => {
    const { 
        layout, 
        fetchLayout, 
        cameraStates, 
        machineStates,
        conveyorBoxes,
        warehouseInventory,
        machineProductionState,
        supervisor,
        operators, 
        maintenanceCrew
    } = useStore();
    
    const containerRef = useRef<HTMLDivElement>(null);
    const [dimensions, setDimensions] = useState({ width: 0, height: 0 });

    useEffect(() => {
        fetchLayout();
    }, [fetchLayout]);
    
    useLayoutEffect(() => {
        const updateSize = () => {
            if (containerRef.current) {
                const { clientWidth, clientHeight } = containerRef.current;
                setDimensions({ width: clientWidth, height: clientHeight });
            }
        };
        updateSize();
        // Resize observer to handle dynamic container resizing
        const resizeObserver = new ResizeObserver(updateSize);
        if (containerRef.current) resizeObserver.observe(containerRef.current);
        return () => resizeObserver.disconnect();
    }, []);

    // Prevent rendering Stage with 0 dimensions (causes InvalidStateError in Konva)
    if (!layout || dimensions.width === 0 || dimensions.height === 0) {
        return (
            <div ref={containerRef} className="w-full h-full bg-slate-900 rounded-lg flex items-center justify-center text-slate-500 text-sm">
                Loading Floor Plan...
            </div>
        );
    }

    const { zones } = layout;
    
    // Layout scaling logic
    // Default to a reasonable size if layout is missing dims (fallback)
    const layoutWidth = layout.dimensions?.width || 800;
    const layoutHeight = layout.dimensions?.height || 600;

    const scaleX = dimensions.width / layoutWidth;
    const scaleY = dimensions.height / layoutHeight;
    // Use 'contain' fit with some padding
    const scale = Math.min(scaleX, scaleY) * 0.95;
    
    const offsetX = (dimensions.width - layoutWidth * scale) / 2;
    const offsetY = (dimensions.height - layoutHeight * scale) / 2;

    return (
        <div ref={containerRef} className="w-full h-full bg-slate-900 rounded-lg overflow-hidden relative shadow-inner">
            <Stage width={dimensions.width} height={dimensions.height}>
                <Layer scaleX={scale} scaleY={scale} x={offsetX} y={offsetY}>
                    
                    {/* Background & Grid */}
                    <Rect width={layoutWidth} height={layoutHeight} fill={THEME.bg} cornerRadius={6} />
                    {/* Simple Grid Lines */}
                    {Array.from({ length: Math.ceil(layoutWidth / 50) }).map((_, i) => (
                        <Rect key={`v-${i}`} x={i * 50} y={0} width={1} height={layoutHeight} fill={THEME.grid} opacity={0.3} />
                    ))}
                    {Array.from({ length: Math.ceil(layoutHeight / 50) }).map((_, i) => (
                        <Rect key={`h-${i}`} x={0} y={i * 50} width={layoutWidth} height={1} fill={THEME.grid} opacity={0.3} />
                    ))}

                    {/* Zones */}
                    {zones.map((zone) => (
                        <ZoneComp key={zone.id} zone={zone as any} />
                    ))}

                    {/* Conveyors */}
                    {layout.conveyors.map((conv) => (
                        <ConveyorComp key={conv.id} conveyor={conv as any} />
                    ))}

                    {/* Machines */}
                    {layout.lines.map((line) => (
                        <MachineStack 
                            key={line.id} 
                            machine={line as any} 
                            productionState={machineProductionState[line.id]} 
                        />
                    ))}

                    {/* Cameras */}
                    {(layout.cameras || []).map((cam) => {
                        const liveState = cameraStates[cam.id];
                        const cameraData = {
                            ...cam,
                            ...liveState, 
                            // Propagate backend color if available, otherwise fallback
                            color: liveState?.color || THEME.camera.body
                        };
                        return <CameraComp key={cam.id} camera={cameraData as any} />;
                    })}

                    {/* Conveyor Boxes */}
                    {Object.values(conveyorBoxes).map((box) => (
                        <ConveyorBoxComp key={box.id} box={box} />
                    ))}
                    
                    {/* Warehouse Inventory */}
                    <WarehouseInventoryDisplay inventory={warehouseInventory} />

                    {/* Operators */}
                    {Object.values(operators).map((op) => (
                        <OperatorComp key={op.id} operator={op as any} />
                    ))}
                    
                    {/* Supervisor */}
                    {supervisor && (
                        <SupervisorComp supervisor={supervisor as any} />
                    )}
                    
                    {/* Maintenance Crew */}
                    {maintenanceCrew && (
                        <MaintenanceCrewComp crew={maintenanceCrew as any} />
                    )}

                </Layer>
            </Stage>
            
            <div className="absolute top-2 right-2 text-xs text-slate-500 font-mono pointer-events-none">
                FloorMap v2.1
            </div>
        </div>
    );
};

// =============================================================================
// SUB-COMPONENTS
// =============================================================================

const ZoneComp: React.FC<{ zone: any }> = ({ zone }) => {
    return (
        <Group x={zone.x} y={zone.y}>
            <Rect
                width={zone.width}
                height={zone.height}
                fill={
                    zone.label.toLowerCase().includes('warehouse') ? THEME.zones.warehouse :
                    zone.label.toLowerCase().includes('break') ? THEME.zones.breakroom :
                    zone.label.toLowerCase().includes('maintenance') ? THEME.zones.maintenance :
                    zone.label.toLowerCase().includes('restricted') ? THEME.zones.restricted :
                    THEME.zones.walkable
                }
                stroke={zone.color}
                strokeWidth={1}
                dash={[4, 4]}
                opacity={0.3}
                cornerRadius={4}
            />
            <Text
                text={zone.label.toUpperCase()}
                fontSize={10}
                fontFamily="Inter, sans-serif"
                fill={zone.color}
                y={8}
                x={8}
                fontStyle="600"
                opacity={0.8}
            />
        </Group>
    );
};

const ConveyorBoxComp: React.FC<{ box: ConveyorBox }> = ({ box }) => {
    return (
        <Rect
            x={box.x}
            y={box.y}
            width={14}
            height={14}
            fill={box.color}
            stroke="#1E293B"
            strokeWidth={1}
            cornerRadius={2}
            shadowColor={box.color}
            shadowBlur={4}
            shadowOpacity={0.4}
        />
    );
};

const WarehouseInventoryDisplay: React.FC<{ inventory: WarehouseInventory }> = ({ inventory }) => {
    const products = Object.entries(inventory).filter(([_, count]) => count > 0);
    const totalBoxes = Object.values(inventory).reduce((a, b) => a + b, 0);
    
    const baseX = 8;
    const baseY = 60;
    
    return (
        <Group x={baseX} y={baseY}>
            <Text text="INVENTORY" fontSize={8} fontFamily="Inter, sans-serif" fill="#F59E0B" fontStyle="600" />
            <Text text={`Total: ${totalBoxes}`} fontSize={9} fontFamily="JetBrains Mono, monospace" fill="#E2E8F0" y={12} />
            {products.map(([type, count], i) => (
                <Group key={type} y={28 + i * 16}>
                    <Circle radius={3} fill={PRODUCT_COLORS[type] || '#FFF'} y={4} />
                    <Text text={`${type.split('_')[1]?.toUpperCase() || type}: ${count}`} x={8} fontSize={9} fill="#94A3B8" fontFamily="JetBrains Mono, monospace" />
                </Group>
            ))}
        </Group>
    );
};

const SupervisorComp: React.FC<{ supervisor: any }> = ({ supervisor }) => {
    const statusColors: Record<string, string> = {
        'idle': '#8B5CF6',
        'moving_to_operator': '#F59E0B',
        'relieving': '#10B981',
        'returning': '#0EA5E9',
    };
    
    const fillColor = statusColors[supervisor.status] || '#8B5CF6';
    const groupRef = useRef<any>(null);
    useEffect(() => {
        if (!groupRef.current) return;
        // IMMEDIATE position update (no animation) to prevent ghost movement
        groupRef.current.position({ x: supervisor.x, y: supervisor.y });
    }, [supervisor.x, supervisor.y]);

    return (
        <Group ref={groupRef} x={supervisor.x} y={supervisor.y}>
            <Circle radius={14} stroke={fillColor} strokeWidth={2} opacity={0.6} />
            <Circle radius={10} fill={fillColor} opacity={0.9} stroke="#FFF" strokeWidth={1} shadowColor={fillColor} shadowBlur={10} />
            <Text text="S" fontSize={10} fontFamily="Inter, sans-serif" fontStyle="bold" fill="#FFF" x={-4} y={-5} />
            <Text text={supervisor.name} fontSize={8} fontFamily="Inter, sans-serif" fill="#E2E8F0" y={18} x={-25} width={50} align="center" />
        </Group>
    );
};

export default FloorMap;
