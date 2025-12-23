import React, { useEffect, useLayoutEffect, useState, useRef } from 'react';
import { Stage, Layer, Rect, Text, Group, Circle, RegularPolygon, Line as KonvaLine } from 'react-konva';
import { useStore } from '../store/useStore';

// Professional color theme - no purple
const THEME = {
    bg: '#0F172A',
    grid: '#1E293B',
    machine: {
        body: '#0EA5E9',      // Sky-500 (cyan-blue)
        equipment: '#0D9488', // Teal-600
        connector: '#475569',
    },
    conveyor: {
        belt: '#64748B',
        running: '#10B981',
        stopped: '#EF4444',
        gradient: ['#334155', '#475569'],
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

const FloorMap: React.FC = () => {
    const { layout, fetchLayout } = useStore();
    const containerRef = useRef<HTMLDivElement>(null);
    const [dimensions, setDimensions] = useState({ width: 0, height: 0 });

    useEffect(() => {
        fetchLayout();
    }, []);
    
    useLayoutEffect(() => {
        const updateSize = () => {
            if (containerRef.current) {
                const { clientWidth, clientHeight } = containerRef.current;
                setDimensions({ width: clientWidth, height: clientHeight });
            }
        };
        updateSize();
        // Small delay to ensure container has sized
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

    // Pattern generation helper
    const createHatchPattern = (color: string) => {
        const canvas = document.createElement('canvas');
        canvas.width = 20;
        canvas.height = 20;
        const ctx = canvas.getContext('2d');
        if (ctx) {
            ctx.strokeStyle = color;
            ctx.lineWidth = 1;
            ctx.beginPath();
            // Diagonal line
            ctx.moveTo(0, 20);
            ctx.lineTo(20, 0);
            ctx.stroke();
        }
        return canvas;
    };
    
    // Pattern state
    const [prodPattern, setProdPattern] = useState<HTMLCanvasElement | null>(null);
    const [warehousePattern, setWarehousePattern] = useState<HTMLCanvasElement | null>(null);
    
    useEffect(() => {
        setProdPattern(createHatchPattern('#334155')); // Slate-700 for production
        setWarehousePattern(createHatchPattern('#FCD34D')); // Amber-300 for warehouse
    }, []);

    if (!layout || dimensions.width === 0) {
        return <div ref={containerRef} className="w-full h-full bg-stone-950 flex items-center justify-center text-stone-500 text-sm">Loading Floor Plan...</div>;
    }

    const { zones, lines, cameras, operators, conveyors } = layout as any;
    const layoutWidth = layout.dimensions.width;
    const layoutHeight = layout.dimensions.height;
    
    const scaleX = dimensions.width / layoutWidth;
    const scaleY = dimensions.height / layoutHeight;
    const scale = Math.min(scaleX, scaleY) * 0.95;
    
    const scaledWidth = layoutWidth * scale;
    const scaledHeight = layoutHeight * scale;
    const offsetX = (dimensions.width - scaledWidth) / 2;
    const offsetY = (dimensions.height - scaledHeight) / 2;

    const getZonePattern = (id: string) => {
        if (id === 'production_floor') return prodPattern;
        if (id === 'warehouse') return warehousePattern;
        return null;
    };

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

                    {/* Conveyors */}
                    {conveyors?.map((conv: ConveyorData) => (
                        <ConveyorComp key={conv.id} conveyor={conv} />
                    ))}

                    {/* Machine Stacks (Production Lines) */}
                    {lines?.map((line: MachineData) => (
                        <MachineStack key={line.id} machine={line} />
                    ))}

                    {/* Operators */}
                    {operators?.map((op: OperatorData) => (
                        <OperatorComp key={op.id} operator={op} />
                    ))}

                    {/* Cameras */}
                    {cameras?.map((cam: CameraData) => (
                        <CameraComp key={cam.id} camera={cam} />
                    ))}
                </Layer>
            </Stage>
        </div>
    );
};

// Zone Component
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
                opacity={pattern ? 0.4 : 1} // Reduced opacity for pattern
            />
            {/* If pattern is used, add a background color rect behind it if needed, or just let stage bg show through */}
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

// Machine Stack Component (Machine + Equipment + Connector to Conveyor)
const MachineStack: React.FC<{ machine: MachineData }> = ({ machine }) => {
    // ... [existing MachineStack implementation]
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
    
    return (
        <Group x={machine.x} y={machine.y}>
            {/* Machine Body (top box) */}
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
            
            {/* Connector from Machine to Equipment */}
            <Rect
                x={machineW / 2 - 2}
                y={machineH}
                width={4}
                height={gap}
                fill={THEME.machine.connector}
            />
            
            {/* Equipment Box (below machine) */}
            <Rect
                x={(machineW - equipW) / 2}
                y={equipY}
                width={equipW}
                height={equipH}
                fill={THEME.machine.equipment}
                cornerRadius={2}
                shadowColor="#000"
                shadowBlur={4}
                shadowOpacity={0.2}
            />
            
            {/* Connector Chute down to Main Conveyor */}
            <Group>
                <Rect
                    x={machineW / 2 - 3}
                    y={connectorStartY}
                    width={6}
                    height={connectorH}
                    fill={THEME.machine.connector}
                    opacity={0.6}
                />
                {/* Arrow head at bottom */}
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
                fill={statusColor}
                shadowColor={statusColor}
                shadowBlur={4}
                shadowOpacity={0.8}
            />
        </Group>
    );
};

// Operator Component
const OperatorComp: React.FC<{ operator: OperatorData }> = ({ operator }) => {
    // ... [existing OperatorComp implementation]
    let fillColor = THEME.operator.idle;
    if (operator.status === 'monitoring') fillColor = THEME.operator.active;
    if (operator.status === 'moving') fillColor = THEME.operator.moving;
    if (operator.status === 'inspecting') fillColor = '#8B5CF6';
    
    return (
        <Group x={operator.x} y={operator.y}>
            <Circle radius={14} fill={fillColor} opacity={0.15} />
            <Circle radius={10} fill={fillColor} opacity={0.7} stroke={fillColor} strokeWidth={2} shadowColor={fillColor} shadowBlur={8} shadowOpacity={0.5} />
            <Circle radius={3} fill="#FFF" opacity={0.9} />
            <Text text={operator.name} fontSize={8} fontFamily="Inter, sans-serif" fill="#E2E8F0" y={16} x={-20} width={40} align="center" />
        </Group>
    );
};

// Conveyor Component
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
            
            {/* Belt stripes (motion indicator) */}
            {isRunning && !isVertical && Array.from({ length: Math.floor(conveyor.width / 20) }).map((_, i) => (
                <Rect
                    key={i}
                    x={i * 20 + 5}
                    y={conveyor.height / 2 - 1}
                    width={10}
                    height={2}
                    fill="#94A3B8"
                    opacity={0.5}
                />
            ))}
            
            {/* Vertical Belt stripes */}
            {isRunning && isVertical && Array.from({ length: Math.floor(conveyor.height / 20) }).map((_, i) => (
                <Rect
                    key={i}
                    y={i * 20 + 5}
                    x={conveyor.width / 2 - 1}
                    height={10}
                    width={2}
                    fill="#94A3B8"
                    opacity={0.5}
                />
            ))}
            
            {/* Status indicator line */}
            <Rect
                x={0}
                y={0}
                width={isVertical ? 3 : conveyor.width}
                height={isVertical ? conveyor.height : 3}
                fill={statusColor}
                cornerRadius={1}
            />
        </Group>
    );
};

// Camera Component
const CameraComp: React.FC<{ camera: CameraData }> = ({ camera }) => {
    const isActive = camera.status === 'active';
    
    return (
        <Group x={camera.x} y={camera.y} rotation={camera.rotation}>
            {/* Camera body */}
            <RegularPolygon
                sides={3}
                radius={6}
                fill={THEME.camera.body}
                stroke={isActive ? THEME.camera.active : '#475569'}
                strokeWidth={1}
            />
            {/* Vision cone */}
            <KonvaLine
                points={[0, 0, -8, 25, 8, 25]}
                closed={true}
                fill={THEME.camera.cone}
                opacity={isActive ? 0.15 : 0.05}
            />
        </Group>
    );
};

export default FloorMap;
