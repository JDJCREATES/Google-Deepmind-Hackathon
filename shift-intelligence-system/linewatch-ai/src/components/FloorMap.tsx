import React, { useEffect, useLayoutEffect, useState, useRef } from 'react';
import Konva from 'konva';
import { Stage, Layer, Rect, Text, Group, Circle, RegularPolygon, Arc } from 'react-konva';
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
    const { 
        layout, 
        fetchLayout, 
        activeOperators, 
        cameraStates, 
        machineStates 
    } = useStore();
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

    // Merge static layout with live state
    const { zones, lines, cameras, operators, conveyors } = layout as any;
    
    // Live Data Overrides
    const liveOperators = operators?.map((op: OperatorData) => ({
        ...op,
        ...(activeOperators[op.id] || {})
    }));

    const liveCameras = cameras?.map((cam: CameraData) => ({
        ...cam,
        ...(cameraStates[cam.id] || {})
    }));

    const liveLines = lines?.map((line: MachineData) => {
        const state = machineStates[line.id];
        return {
            ...line,
            health: state ? state.health : line.health,
            // throughput: state ? state.throughput : 0, // could use for particle speed
        };
    });

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

                    {/* Conveyors (Bottom Layer) */}
                    {conveyors?.map((conv: ConveyorData) => (
                        <ConveyorComp key={conv.id} conveyor={conv} />
                    ))}

                    {/* Machine Stacks (Production Lines) */}
                    {liveLines?.map((line: MachineData) => (
                        <MachineStack key={line.id} machine={line} />
                    ))}

                    {/* Operators (Middle Layer) */}
                    {liveOperators?.map((op: OperatorData) => (
                        <OperatorComp key={op.id} operator={op} />
                    ))}

                    {/* Cameras (Top Layer for cones) */}
                    {liveCameras?.map((cam: CameraData) => (
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

// Animated Operator Component
const OperatorComp: React.FC<{ operator: OperatorData }> = ({ operator }) => {
    const groupRef = useRef<any>(null);
    
    // Tween movement when position changes
    useEffect(() => {
        if (!groupRef.current) return;
        
        // Kill previous tweens if any
        groupRef.current.to({
            x: operator.x,
            y: operator.y,
            duration: 4.0, // 4s transition (slightly faster than 5s tick for responsiveness)
            easing: Konva.Easings.EaseInOut,
        });
    }, [operator.x, operator.y]);

    let fillColor = THEME.operator.idle;
    if (operator.status === 'monitoring') fillColor = THEME.operator.active;
    if (operator.status === 'moving') fillColor = THEME.operator.moving;
    if (operator.status === 'inspecting') fillColor = '#8B5CF6';
    
    // Use initial position for first render, then tween takes over
    // logic: We render at the TARGET position initially if it's the very first mount? 
    // Actually, storing the "current" pos in state is hard.
    // Konva handles it: if we change key/prop 'x', React-Konva updates immediately.
    // To animate, we must NOT bind x/y to props directly after mount, OR use the ref to override.
    // But React-Konva will try to reset it on re-render.
    // Solution: Pass initial x/y only? No, just let the tween override.
    
    return (
        <Group 
            ref={groupRef}
            x={operator.x} // Note: This will jump on update if we don't handle it carefully.
                           // Actually, simpler: Use a separate "visualPosition" state if we want perfect control.
                           // But Konva.to() modifies the node instance directly. React-Konva usually respects that until props change.
                           // Since props CHANGE every 5s, we trigger the tween then.
            y={operator.y}
        >
            <Circle radius={14} fill={fillColor} opacity={0.15} />
            <Circle radius={10} fill={fillColor} opacity={0.7} stroke={fillColor} strokeWidth={2} shadowColor={fillColor} shadowBlur={8} shadowOpacity={0.5} />
            <Circle radius={3} fill="#FFF" opacity={0.9} />
            <Text text={operator.name} fontSize={8} fontFamily="Inter, sans-serif" fill="#E2E8F0" y={16} x={-20} width={40} align="center" />
        </Group>
    );
};

// Product Stream Component for Conveyors
const ProductStream: React.FC<{ 
    conv: ConveyorData, 
    boxColor: string, 
    size: number 
}> = ({ conv, boxColor, size }) => {
    // Determine flow direction and limits
    const isVertical = conv.direction === 'vertical';
    const length = isVertical ? conv.height : conv.width;
    const isReverse = (conv as any).flow === 'reverse'; // Type assertion for custom prop
    
    // Create particles
    const particleCount = Math.floor(length / 40); // 1 box every 40px
    const particles = Array.from({ length: particleCount }).map((_, i) => i);

    return (
        <Group x={0} y={0}>
             {particles.map((i) => (
                 <ProductBox 
                    key={i} 
                    index={i} 
                    total={particleCount} 
                    length={length} 
                    isVertical={isVertical} 
                    isReverse={isReverse}
                    color={boxColor} 
                    size={size}
                    speed={4000} // Slower speed (4s loop)
                 />
             ))}
        </Group>
    );
};

const ProductBox: React.FC<{
    index: number,
    total: number,
    length: number,
    isVertical: boolean,
    isReverse: boolean,
    color: string,
    size: number,
    speed: number
}> = ({ index, total, length, isVertical, isReverse, color, size, speed }) => {
    const ref = useRef<any>(null);

    useEffect(() => {
        if (!ref.current) return;
        
        // Continuous loop animation
        const anim = new Konva.Animation((frame) => {
            if (!frame) return;
            const time = frame.time + (index * (speed / total));
            const progress = (time % speed) / speed;
            
            // Calculate Position
            let pos = progress * length;
            if (isReverse) {
                pos = length - pos; // Move backwards
            }
            
            if (isVertical) {
                ref.current.y(pos);
            } else {
                ref.current.x(pos);
            }
            
            // Fade in/out at edges
            let opacity = 1;
            // Standard fade logic (near 0 and near length)
            // If reverse, logical start is length.
            // But progress 0..1 maps to movement.
            // Edge fading based on progress works regardless of direction
            if (progress < 0.1) opacity = progress * 10;
            if (progress > 0.9) opacity = (1 - progress) * 10;
            ref.current.opacity(opacity);
            
        }, ref.current.getLayer());
        
        anim.start();
        return () => {
            anim.stop();
        };
    }, [index, total, length, speed, isVertical, isReverse]);

    return (
        <Rect
            ref={ref}
            x={isVertical ? (30 - size)/2 : 0} 
            y={isVertical ? 0 : (10 - size)/2}
            width={size}
            height={size}
            fill={color}
            cornerRadius={1}
        />
    );
}

// Conveyor Component
const ConveyorComp: React.FC<{ conveyor: ConveyorData }> = ({ conveyor }) => {
    const isRunning = conveyor.status === 'running';
    const statusColor = isRunning ? THEME.conveyor.running : THEME.conveyor.stopped;
    const isVertical = conveyor.direction === 'vertical';
    
    // Distinguish Main vs Feeder
    const isMain = conveyor.id.includes('main');
    
    // Box style
    const boxSize = isMain ? 12 : 6;
    const boxColor = isMain ? '#FCD34D' : '#94A3B8'; // Gold (Packed) vs Slate (Raw)

    return (
        <Group x={conveyor.x} y={conveyor.y}>
            {/* Belt background */}
            <Rect
                width={conveyor.width}
                height={conveyor.height}
                fill={THEME.conveyor.belt}
                cornerRadius={2}
            />
            
            {/* Product Stream (Only if running) */}
            {isRunning && (
                <ProductStream 
                    conv={conveyor} 
                    boxColor={boxColor} 
                    size={boxSize} 
                />
            )}
            
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
    
    // Calculate Cone Points based on FOV and Range
    // (0,0) is camera tip.
    // Base rotation 0 points DOWN in this coordinate system for Konva setup? 
    // Previous code [0,0, -8, 25, 8, 25] implies Y+ is the direction.
    // So let's calculate angles relative to "DOWN" (90 deg).
    // Actually, simple math:
    // Left point X = length * sin(-fov/2)
    // Left point Y = length * cos(-fov/2)
    // etc.
    
    const range = camera.range || 100;
    const fov = camera.fov || 60;
    
    // Cone visual properties
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
                rotation={180} // Point triangle down relative to group
            />
             {/* Vision cone (Single Uniform Arc) */}
             <Arc
                innerRadius={0}
                outerRadius={range}
                angle={fov}
                rotation={90 - (fov/2)} // Center the arc downwards
                fill={coneColor}
                opacity={isActive ? 0.2 : 0.05}
                stroke={isActive ? coneColor : 'transparent'}
                strokeWidth={1}
            />
        </Group>
    );
};

export default FloorMap;
