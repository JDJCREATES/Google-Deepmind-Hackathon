import React, { useEffect, useLayoutEffect, useState, useRef } from 'react';
import Konva from 'konva';
import { Stage, Layer, Rect, Text, Group, Circle, RegularPolygon, Arc } from 'react-konva';
import { useStore, type ConveyorBox, type MachineProductionState, type WarehouseInventory } from '../store/useStore';

// =============================================================================
// THEME & CONSTANTS
// =============================================================================

const THEME = {
    bg: '#0F172A',
    grid: '#1E293B',
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

// Product colors for inventory display
const PRODUCT_COLORS: Record<string, string> = {
    widget_a: '#3B82F6',
    widget_b: '#10B981',
    gizmo_x: '#F59E0B',
    gizmo_y: '#EF4444',
    part_z: '#8B5CF6',
};

// =============================================================================
// TYPE DEFINITIONS
// =============================================================================

interface MachineData {
    id: number;
    label: string;
    x: number;
    y: number;
    machine_w: number;
    machine_h: number;
    equip_w: number;
    equip_h: number;
    connector_h?: number;
    status: string;
    health: number;
}

interface OperatorData {
    id: string;
    name: string;
    x: number;
    y: number;
    status: string;
    assigned_lines: number[];
}

interface ConveyorData {
    id: string;
    x: number;
    y: number;
    width: number;
    height: number;
    direction: string;
    status: string;
}

interface CameraData {
    id: string;
    line_id: number;
    x: number;
    y: number;
    rotation: number;
    fov: number;
    range: number;
    label: string;
    status: string;
}

interface ZoneData {
    id: string;
    x: number;
    y: number;
    width: number;
    height: number;
    label: string;
    color: string;
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

const FloorMap: React.FC = () => {
    const { 
        layout, 
        fetchLayout, 
        activeOperators, 
        cameraStates, 
        machineStates,
        // Production System (NEW)
        conveyorBoxes,
        warehouseInventory,
        machineProductionState,
        // Supervisor & Fatigue (NEW)
        supervisor,
        operators: operatorsWithFatigue,
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
        const timeout = setTimeout(updateSize, 100);
        return () => clearTimeout(timeout);
    }, []);
    
    useEffect(() => {
        const updateSize = () => {
            if (containerRef.current) {
                const { clientWidth, clientHeight } = containerRef.current;
                setDimensions({ width: clientWidth, height: clientHeight });
            }
        };
        window.addEventListener('resize', updateSize);
        const resizeObserver = new ResizeObserver(updateSize);
        if (containerRef.current) resizeObserver.observe(containerRef.current);
        return () => {
            window.removeEventListener('resize', updateSize);
            resizeObserver.disconnect();
        };
    }, []);

    // Pattern generation for zones
    const createHatchPattern = (color: string) => {
        const canvas = document.createElement('canvas');
        canvas.width = 20;
        canvas.height = 20;
        const ctx = canvas.getContext('2d');
        if (ctx) {
            ctx.strokeStyle = color;
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(0, 20);
            ctx.lineTo(20, 0);
            ctx.stroke();
        }
        return canvas;
    };
    
    const [prodPattern, setProdPattern] = useState<HTMLCanvasElement | null>(null);
    const [warehousePattern, setWarehousePattern] = useState<HTMLCanvasElement | null>(null);
    
    useEffect(() => {
        setProdPattern(createHatchPattern('#334155'));
        setWarehousePattern(createHatchPattern('#FCD34D'));
    }, []);

    if (!layout || dimensions.width === 0) {
        return <div ref={containerRef} className="w-full h-full bg-stone-950 flex items-center justify-center text-stone-500 text-sm">Loading Floor Plan...</div>;
    }

    const { zones, lines, cameras, operators, conveyors } = layout as any;
    
    // Merge static layout with live state
    const liveOperators = operators?.map((op: OperatorData) => ({
        ...op,
        ...(activeOperators[op.id] || {})
    }));

    const liveCameras = cameras?.map((cam: CameraData) => ({
        ...cam,
        ...(cameraStates[cam.id] || {})
    }));

    const liveLines = lines?.map((line: MachineData) => {
        const healthState = machineStates[line.id];
        const prodState = machineProductionState[line.id];
        return {
            ...line,
            health: healthState ? healthState.health : line.health,
            productionState: prodState,
        };
    });

    const layoutWidth = layout.dimensions.width;
    const layoutHeight = layout.dimensions.height;
    
    const scaleX = dimensions.width / layoutWidth;
    const scaleY = dimensions.height / layoutHeight;
    const scale = Math.min(scaleX, scaleY) * 0.95;
    
    const offsetX = (dimensions.width - layoutWidth * scale) / 2;
    const offsetY = (dimensions.height - layoutHeight * scale) / 2;

    const getZonePattern = (id: string) => {
        if (id === 'production_floor') return prodPattern;
        if (id === 'warehouse') return warehousePattern;
        return null;
    };

    // Convert conveyor boxes object to array
    const conveyorBoxArray = Object.values(conveyorBoxes);

    return (
        <div ref={containerRef} className="w-full h-full overflow-hidden bg-stone-950">
            <Stage width={dimensions.width} height={dimensions.height}>
                <Layer scaleX={scale} scaleY={scale} x={offsetX} y={offsetY}>
                    {/* Background */}
                    <Rect x={0} y={0} width={layoutWidth} height={layoutHeight} fill={THEME.bg} cornerRadius={6} />
                    
                    {/* Zones */}
                    {zones?.map((zone: ZoneData) => (
                        <ZoneComp key={zone.id} zone={zone} pattern={getZonePattern(zone.id)} />
                    ))}

                    {/* Warehouse Inventory Display (NEW) */}
                    <WarehouseInventoryDisplay inventory={warehouseInventory} />

                    {/* Conveyors (Bottom Layer) */}
                    {conveyors?.map((conv: ConveyorData) => (
                        <ConveyorComp key={conv.id} conveyor={conv} />
                    ))}

                    {/* Real Conveyor Boxes (NEW) */}
                    {conveyorBoxArray.map((box) => (
                        <ConveyorBoxComp key={box.id} box={box} />
                    ))}

                    {/* Machine Stacks with Production State */}
                    {liveLines?.map((line: MachineData & { productionState?: MachineProductionState }) => (
                        <MachineStack key={line.id} machine={line} productionState={line.productionState} />
                    ))}

                    {/* Operators */}
                    {liveOperators?.map((op: OperatorData) => (
                        <OperatorComp key={op.id} operator={op} />
                    ))}
                    
                    {/* Fatigue Bars (NEW) - Render above operators */}
                    {Object.values(operatorsWithFatigue).map((op) => (
                        <FatigueBar 
                            key={`fatigue-${op.id}`} 
                            x={op.x} 
                            y={op.y} 
                            fatigue={op.fatigue} 
                            onBreak={op.on_break} 
                        />
                    ))}
                    
                    {/* Supervisor (NEW) */}
                    {supervisor && (
                        <SupervisorComp supervisor={supervisor} />
                    )}

                    {/* Cameras */}
                    {liveCameras?.map((cam: CameraData) => (
                        <CameraComp key={cam.id} camera={cam} />
                    ))}
                </Layer>
            </Stage>
        </div>
    );
};

// =============================================================================
// ZONE COMPONENT
// =============================================================================

const ZoneComp: React.FC<{ zone: ZoneData, pattern?: HTMLCanvasElement | null }> = ({ zone, pattern }) => {
    return (
        <Group x={zone.x} y={zone.y}>
            <Rect
                width={zone.width}
                height={zone.height}
                fill={pattern ? undefined : zone.color + '15'}
                fillPatternImage={pattern as any}
                fillPatternRepeat="repeat"
                stroke={zone.color}
                strokeWidth={1.5}
                cornerRadius={4}
                opacity={pattern ? 0.4 : 1}
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

// =============================================================================
// WAREHOUSE INVENTORY DISPLAY (NEW)
// =============================================================================

const WarehouseInventoryDisplay: React.FC<{ inventory: WarehouseInventory }> = ({ inventory }) => {
    const products = Object.entries(inventory).filter(([_, count]) => count > 0);
    const totalBoxes = Object.values(inventory).reduce((a, b) => a + b, 0);
    
    // Position in warehouse zone (left side of canvas)
    const baseX = 8;
    const baseY = 60;
    
    return (
        <Group x={baseX} y={baseY}>
            {/* Title */}
            <Text
                text="INVENTORY"
                fontSize={8}
                fontFamily="Inter, sans-serif"
                fill="#F59E0B"
                fontStyle="600"
            />
            
            {/* Total Count */}
            <Text
                text={`Total: ${totalBoxes}`}
                fontSize={9}
                fontFamily="JetBrains Mono, monospace"
                fill="#E2E8F0"
                y={12}
            />
            
            {/* Product breakdown */}
            {products.map(([type, count], i) => (
                <Group key={type} y={28 + i * 16}>
                    {/* Color indicator */}
                    <Rect
                        x={0}
                        y={0}
                        width={10}
                        height={10}
                        fill={PRODUCT_COLORS[type] || '#666'}
                        cornerRadius={2}
                    />
                    {/* Count */}
                    <Text
                        x={14}
                        y={0}
                        text={`${count}`}
                        fontSize={9}
                        fontFamily="JetBrains Mono, monospace"
                        fill="#E2E8F0"
                    />
                </Group>
            ))}
            
            {/* Visual box stack representation */}
            <Group y={28 + products.length * 16 + 10}>
                {Array.from({ length: Math.min(totalBoxes, 20) }).map((_, i) => {
                    const row = Math.floor(i / 4);
                    const col = i % 4;
                    return (
                        <Rect
                            key={i}
                            x={col * 14}
                            y={-row * 12}  // Stack upward
                            width={12}
                            height={10}
                            fill="#78350F"
                            stroke="#92400E"
                            strokeWidth={0.5}
                            cornerRadius={1}
                        />
                    );
                })}
                {totalBoxes > 20 && (
                    <Text
                        x={0}
                        y={14}
                        text={`+${totalBoxes - 20} more`}
                        fontSize={7}
                        fill="#94A3B8"
                    />
                )}
            </Group>
        </Group>
    );
};

// =============================================================================
// CONVEYOR BOX COMPONENT (NEW - Real boxes from backend)
// =============================================================================

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

// =============================================================================
// MACHINE STACK COMPONENT (Updated with fill indicator)
// =============================================================================

const MachineStack: React.FC<{ 
    machine: MachineData, 
    productionState?: MachineProductionState 
}> = ({ machine, productionState }) => {
    const health = machine.health ?? 100;
    let statusColor = THEME.status.ok;
    if (health < 80) statusColor = THEME.status.warning;
    if (health < 40) statusColor = THEME.status.critical;
    
    const machineW = machine.machine_w || 35;
    const machineH = machine.machine_h || 45;
    const equipW = machine.equip_w || 28;
    const equipH = machine.equip_h || 30;
    const connectorH = machine.connector_h || 15;
    
    const gap = 4;
    const equipY = machineH + gap;
    const connectorStartY = equipY + equipH;
    
    // Production state
    const fillLevel = productionState?.fill_level || 0;
    const productColor = productionState?.product_color || THEME.machine.equipment;
    const isRunning = productionState?.is_running !== false;
    
    return (
        <Group x={machine.x} y={machine.y}>
            {/* Machine Body */}
            <Rect
                x={0}
                y={0}
                width={machineW}
                height={machineH}
                fill={THEME.machine.body}
                stroke={statusColor}
                strokeWidth={2}
                cornerRadius={3}
                shadowColor="#000"
                shadowBlur={6}
                shadowOpacity={0.3}
            />
            
            {/* Machine Label */}
            <Text
                text={machine.label}
                fontSize={8}
                fontFamily="JetBrains Mono, monospace"
                fill="#FFF"
                x={0}
                y={machineH / 2 - 4}
                width={machineW}
                align="center"
            />
            
            {/* Connector */}
            <Rect
                x={machineW / 2 - 2}
                y={machineH}
                width={4}
                height={gap}
                fill={THEME.machine.connector}
            />
            
            {/* Equipment Box Background */}
            <Rect
                x={(machineW - equipW) / 2}
                y={equipY}
                width={equipW}
                height={equipH}
                fill="#2D3748"
                cornerRadius={2}
            />
            
            {/* Fill Level Indicator (renders inside equipment box) */}
            <Rect
                x={(machineW - equipW) / 2}
                y={equipY + equipH - (equipH * fillLevel / 100)}
                width={equipW}
                height={equipH * fillLevel / 100}
                fill={isRunning ? productColor : '#475569'}
                cornerRadius={2}
                opacity={isRunning ? 0.9 : 0.3}
            />
            
            {/* Equipment Box Border */}
            <Rect
                x={(machineW - equipW) / 2}
                y={equipY}
                width={equipW}
                height={equipH}
                stroke={isRunning ? productColor : '#475569'}
                strokeWidth={1.5}
                cornerRadius={2}
                shadowColor="#000"
                shadowBlur={4}
                shadowOpacity={0.2}
            />
            
            {/* Connector Chute */}
            <Group>
                <Rect
                    x={machineW / 2 - 3}
                    y={connectorStartY}
                    width={6}
                    height={connectorH}
                    fill={THEME.machine.connector}
                    opacity={0.6}
                />
                <RegularPolygon
                    sides={3}
                    radius={5}
                    x={machineW / 2}
                    y={connectorStartY + connectorH - 2}
                    rotation={180}
                    fill={THEME.machine.connector}
                />
            </Group>
            
            {/* Status Indicator LED */}
            <Circle
                x={machineW - 5}
                y={5}
                radius={3}
                fill={isRunning ? statusColor : THEME.status.critical}
                shadowColor={isRunning ? statusColor : THEME.status.critical}
                shadowBlur={4}
                shadowOpacity={0.8}
            />
            
            {/* Running indicator pulse */}
            {isRunning && fillLevel > 0 && (
                <Circle
                    x={machineW / 2}
                    y={equipY + equipH / 2}
                    radius={2}
                    fill="#FFF"
                    opacity={0.6}
                />
            )}
        </Group>
    );
};

// =============================================================================
// OPERATOR COMPONENT
// =============================================================================

const OperatorComp: React.FC<{ operator: OperatorData }> = ({ operator }) => {
    const groupRef = useRef<any>(null);
    
    useEffect(() => {
        if (!groupRef.current) return;
        
        groupRef.current.to({
            x: operator.x,
            y: operator.y,
            duration: 0.8,
            easing: Konva.Easings.EaseInOut,
        });
    }, [operator.x, operator.y]);

    let fillColor = THEME.operator.idle;
    if (operator.status === 'monitoring') fillColor = THEME.operator.active;
    if (operator.status === 'moving') fillColor = THEME.operator.moving;
    if (operator.status === 'inspecting') fillColor = '#8B5CF6';
    if (operator.status === 'working') fillColor = THEME.operator.active;
    
    return (
        <Group 
            ref={groupRef}
            x={operator.x}
            y={operator.y}
        >
            <Circle radius={14} fill={fillColor} opacity={0.15} />
            <Circle radius={10} fill={fillColor} opacity={0.7} stroke={fillColor} strokeWidth={2} shadowColor={fillColor} shadowBlur={8} shadowOpacity={0.5} />
            <Circle radius={3} fill="#FFF" opacity={0.9} />
            <Text text={operator.name} fontSize={8} fontFamily="Inter, sans-serif" fill="#E2E8F0" y={16} x={-20} width={40} align="center" />
        </Group>
    );
};

// =============================================================================
// SUPERVISOR COMPONENT (NEW)
// =============================================================================

interface SupervisorCompProps {
    supervisor: {
        id: string;
        name: string;
        x: number;
        y: number;
        status: string;
        current_action: string;
    };
}

const SupervisorComp: React.FC<SupervisorCompProps> = ({ supervisor }) => {
    // Distinct color scheme for supervisor
    const statusColors: Record<string, string> = {
        'idle': '#8B5CF6',  // Purple
        'moving_to_operator': '#F59E0B',  // Amber
        'relieving': '#10B981',  // Green
        'returning': '#0EA5E9',  // Blue
    };
    
    const fillColor = statusColors[supervisor.status] || '#8B5CF6';
    
    return (
        <Group x={supervisor.x} y={supervisor.y}>
            {/* Outer ring to distinguish from operators */}
            <Circle 
                radius={14} 
                stroke={fillColor} 
                strokeWidth={2} 
                opacity={0.6}
            />
            {/* Main body */}
            <Circle 
                radius={10} 
                fill={fillColor} 
                opacity={0.9} 
                stroke="#FFF" 
                strokeWidth={1}
                shadowColor={fillColor} 
                shadowBlur={10} 
                shadowOpacity={0.7} 
            />
            {/* Icon indicator (S for Supervisor) */}
            <Text 
                text="S" 
                fontSize={10} 
                fontFamily="Inter, sans-serif" 
                fontStyle="bold"
                fill="#FFF" 
                x={-4} 
                y={-5} 
            />
            {/* Name label */}
            <Text 
                text={supervisor.name} 
                fontSize={8} 
                fontFamily="Inter, sans-serif" 
                fill="#E2E8F0" 
                y={18} 
                x={-25} 
                width={50} 
                align="center" 
            />
        </Group>
    );
};

// =============================================================================
// FATIGUE BAR COMPONENT (NEW)
// =============================================================================

interface FatigueBarProps {
    x: number;
    y: number;
    fatigue: number;  // 0-100
    onBreak: boolean;
}

const FatigueBar: React.FC<FatigueBarProps> = ({ x, y, fatigue, onBreak }) => {
    // Don't show bar if on break
    if (onBreak) {
        return (
            <Group x={x} y={y - 20}>
                <Rect
                    x={-15}
                    y={0}
                    width={30}
                    height={12}
                    fill="#0EA5E9"
                    cornerRadius={2}
                    opacity={0.8}
                />
                <Text
                    text="BREAK"
                    fontSize={7}
                    fontFamily="Inter, sans-serif"
                    fontStyle="bold"
                    fill="#FFF"
                    x={-15}
                    y={2}
                    width={30}
                    align="center"
                />
            </Group>
        );
    }
    
    // Color based on fatigue level
    const getColor = (level: number) => {
        if (level < 40) return '#10B981';  // Green - fresh
        if (level < 70) return '#F59E0B';  // Amber - getting tired
        return '#EF4444';  // Red - exhausted
    };
    
    const barWidth = 30;
    const barHeight = 4;
    const fillWidth = (fatigue / 100) * barWidth;
    const color = getColor(fatigue);
    
    return (
        <Group x={x} y={y - 18}>
            {/* Background */}
            <Rect
                x={-barWidth / 2}
                y={0}
                width={barWidth}
                height={barHeight}
                fill="#1E293B"
                cornerRadius={2}
                stroke="#475569"
                strokeWidth={0.5}
            />
            {/* Fill */}
            <Rect
                x={-barWidth / 2}
                y={0}
                width={fillWidth}
                height={barHeight}
                fill={color}
                cornerRadius={2}
            />
            {/* Percentage text (only if > 50%) */}
            {fatigue > 50 && (
                <Text
                    text={`${Math.round(fatigue)}%`}
                    fontSize={6}
                    fontFamily="Inter, sans-serif"
                    fill="#E2E8F0"
                    x={-barWidth / 2}
                    y={-8}
                    width={barWidth}
                    align="center"
                />
            )}
        </Group>
    );
};

// =============================================================================
// CONVEYOR COMPONENT (Simplified - no fake animations)
// =============================================================================

const ConveyorComp: React.FC<{ conveyor: ConveyorData }> = ({ conveyor }) => {
    const isRunning = conveyor.status === 'running';
    const statusColor = isRunning ? THEME.conveyor.running : THEME.conveyor.stopped;
    const isVertical = conveyor.direction === 'vertical';

    return (
        <Group x={conveyor.x} y={conveyor.y}>
            {/* Belt background */}
            <Rect
                width={conveyor.width}
                height={conveyor.height}
                fill={THEME.conveyor.belt}
                cornerRadius={2}
            />
            
            {/* Status indicator line */}
            <Rect
                x={0}
                y={0}
                width={isVertical ? 3 : conveyor.width}
                height={isVertical ? conveyor.height : 3}
                fill={statusColor}
                cornerRadius={1}
            />
            
            {/* Direction arrows (visual hint) */}
            {isRunning && !isVertical && (
                <Group>
                    {Array.from({ length: Math.floor(conveyor.width / 60) }).map((_, i) => (
                        <Text
                            key={i}
                            x={conveyor.width - 20 - i * 60}
                            y={conveyor.height / 2 - 4}
                            text="◀"
                            fontSize={8}
                            fill="#94A3B8"
                            opacity={0.5}
                        />
                    ))}
                </Group>
            )}
        </Group>
    );
};

// =============================================================================
// CAMERA COMPONENT
// =============================================================================

const CameraComp: React.FC<{ camera: CameraData }> = ({ camera }) => {
    const isActive = camera.status === 'active';
    const range = camera.range || 100;
    const fov = camera.fov || 60;
    const coneColor = isActive ? THEME.camera.active : THEME.camera.cone;

    return (
        <Group x={camera.x} y={camera.y} rotation={camera.rotation}>
            {/* Camera body */}
            <RegularPolygon
                sides={3}
                radius={8}
                fill={THEME.camera.body}
                stroke={isActive ? THEME.camera.active : '#475569'}
                strokeWidth={1}
                rotation={180}
            />
            {/* Vision cone */}
            <Arc
                innerRadius={0}
                outerRadius={range}
                angle={fov}
                rotation={90 - (fov/2)}
                fill={coneColor}
                opacity={isActive ? 0.2 : 0.05}
                stroke={isActive ? coneColor : 'transparent'}
                strokeWidth={1}
            />
        </Group>
    );
};

export default FloorMap;
