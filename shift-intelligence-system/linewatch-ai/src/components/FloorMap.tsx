import React, { useEffect, useState, useRef } from 'react';
import { Stage, Layer, Rect, Text, Group, RegularPolygon, Line as KonvaLine } from 'react-konva';
import { useStore } from '../store/useStore';
import type { Line, Camera, Zone } from '../types';

const THEME = {
    bg: '#1C1917',
    grid: '#292524',
    zone: {
        production: '#292524',
        break_room: '#1C1917',
    },
    line: {
        ok: '#10B981',
        warning: '#F59E0B',
        critical: '#EF4444',
    }
};

const FloorMap: React.FC = () => {
    const { layout, fetchLayout } = useStore();
    const containerRef = useRef<HTMLDivElement>(null);
    const [dimensions, setDimensions] = useState({ width: 600, height: 400 });

    useEffect(() => {
        fetchLayout();
    }, []);
    
    // Responsive sizing
    useEffect(() => {
        const updateSize = () => {
            if (containerRef.current) {
                const { clientWidth, clientHeight } = containerRef.current;
                setDimensions({ width: clientWidth, height: clientHeight });
            }
        };
        
        updateSize();
        window.addEventListener('resize', updateSize);
        
        // ResizeObserver for container changes
        const resizeObserver = new ResizeObserver(updateSize);
        if (containerRef.current) {
            resizeObserver.observe(containerRef.current);
        }
        
        return () => {
            window.removeEventListener('resize', updateSize);
            resizeObserver.disconnect();
        };
    }, []);

    if (!layout) return <div className="p-6 text-stone-500 text-sm">Loading Floor Plan...</div>;

    const { zones, lines, cameras } = layout;
    
    // Calculate scale to fit layout in container
    const layoutWidth = layout.dimensions.width;
    const layoutHeight = layout.dimensions.height;
    const scaleX = (dimensions.width - 20) / layoutWidth;
    const scaleY = (dimensions.height - 20) / layoutHeight;
    const scale = Math.min(scaleX, scaleY, 1);

    return (
        <div ref={containerRef} className="w-full h-full overflow-hidden bg-stone-900">
            <Stage 
                width={dimensions.width} 
                height={dimensions.height} 
                scaleX={scale} 
                scaleY={scale}
                x={10}
                y={10}
            >
                <Layer>
                    {/* Background */}
                    <Rect x={0} y={0} width={layoutWidth} height={layoutHeight} fill={THEME.bg} cornerRadius={4} />
                    
                    {/* Zones */}
                    {zones.map((zone) => (
                        <ZoneComp key={zone.id} zone={zone} />
                    ))}

                    {/* Production Lines */}
                    {lines.map((line) => (
                        <LineComp key={line.id} line={line} />
                    ))}

                    {/* Cameras */}
                    {cameras.map((cam) => (
                        <CameraComp key={cam.id} camera={cam} />
                    ))}
                </Layer>
            </Stage>
        </div>
    );
};

const ZoneComp: React.FC<{ zone: Zone }> = ({ zone }) => {
    return (
        <Group x={zone.x} y={zone.y}>
            <Rect
                width={zone.width}
                height={zone.height}
                fill={zone.color + '20'} // Low opacity
                stroke={zone.color}
                strokeWidth={2}
                cornerRadius={4}
            />
            <Text
                text={zone.label.toUpperCase()}
                fontSize={14}
                fontFamily="Inter"
                fill={zone.color}
                y={10}
                x={10}
                fontStyle="bold"
            />
        </Group>
    );
};

const LineComp: React.FC<{ line: Line & { health?: number } }> = ({ line }) => {
    // Determine color based on health (mock logic if not provided)
    const health = line.health ?? 100;
    let fill = THEME.line.ok;
    if (health < 80) fill = THEME.line.warning;
    if (health < 40) fill = THEME.line.critical;

    return (
        <Group x={line.x} y={line.y}>
            {/* Conveyor Belt */}
            <Rect
                width={line.width}
                height={line.height}
                fill="#334155" // Dark belt
                cornerRadius={2}
            />
            {/* Status Indicator (Bar on top) */}
            <Rect
                x={0}
                y={-4}
                width={line.width * (health / 100)}
                height={4}
                fill={fill}
            />
            <Text
                text={line.label}
                fill="#F8FAFC"
                fontSize={12}
                x={10}
                y={12}
                fontFamily="JetBrains Mono"
            />
        </Group>
    );
};

const CameraComp: React.FC<{ camera: Camera }> = ({ camera }) => {
    return (
        <Group x={camera.x} y={camera.y} rotation={camera.rotation}>
            {/* Camera Body */}
            <RegularPolygon
                sides={3}
                radius={8}
                fill="#1E293B"
            />
            {/* Vision Cone (Semi-transparent) */}
            <KonvaLine
                points={[0, 0, -20, 60, 20, 60]}
                closed={true}
                fill="#FCD34D"
                opacity={0.2}
                stroke="#FCD34D"
                strokeWidth={1}
            />
        </Group>
    );
};

export default FloorMap;
