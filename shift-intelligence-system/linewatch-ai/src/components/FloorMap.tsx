import React, { useEffect, useState } from 'react';
import { Stage, Layer, Rect, Text, Group, RegularPolygon, Line as KonvaLine } from 'react-konva';
import { useStore } from '../store/useStore';
import type { Line, Camera, Zone } from '../types';

const THEME = {
    bg: '#FDFBF7',
    grid: '#E5E7EB',
    zone: {
        production: '#E2E8F0', // slate-200
        break_room: '#F1F5F9', // slate-100
    },
    line: {
        ok: '#10B981', // emerald-500
        warning: '#F59E0B', // amber-500
        critical: '#EF4444', // red-500
    }
};

const FloorMap: React.FC = () => {
    const { layout, fetchLayout } = useStore();
    const [scale] = useState(0.8); // Adjust to fit screen

    useEffect(() => {
        fetchLayout();
    }, []);

    if (!layout) return <div className="p-10 text-stone-500">Loading Floor Plan...</div>;

    const { zones, lines, cameras } = layout;

    return (
        <div className="w-full h-full overflow-hidden bg-background border border-gray-200 rounded-md shadow-sm">
            <Stage width={window.innerWidth * 0.7} height={600} scaleX={scale} scaleY={scale}>
                <Layer>
                    {/* Background Grid (Optional) */}
                    <Rect x={0} y={0} width={layout.dimensions.width} height={layout.dimensions.height} fill={THEME.bg} />
                    
                    {/* 1. Zones */}
                    {zones.map((zone) => (
                        <ZoneComp key={zone.id} zone={zone} />
                    ))}

                    {/* 2. Production Lines */}
                    {lines.map((line) => (
                        <LineComp key={line.id} line={line} />
                    ))}

                    {/* 3. Cameras */}
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
