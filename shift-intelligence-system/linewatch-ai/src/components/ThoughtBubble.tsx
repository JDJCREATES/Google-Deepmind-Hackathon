import React, { useEffect, useState } from 'react';

interface ThoughtBubbleProps {
    id: string;
    text: string;
    agentColor: string;
    onComplete: (id: string) => void;
}

const ThoughtBubble: React.FC<ThoughtBubbleProps> = ({ id, text, agentColor, onComplete }) => {
    const [isVisible, setIsVisible] = useState(true);

    useEffect(() => {
        // Auto-remove after animation completes
        const timer = setTimeout(() => {
            setIsVisible(false);
            onComplete(id);
        }, 8000); // 8 seconds total

        return () => clearTimeout(timer);
    }, [id, onComplete]);

    if (!isVisible) return null;

    return (
        <div
            className="absolute pointer-events-none"
            style={{
                animation: 'thoughtDrift 8s ease-out forwards',
                zIndex: 1000,
            }}
        >
            <div
                className="relative bg-stone-900/95 border-2 rounded-2xl px-3 py-2 max-w-[200px] shadow-lg"
                style={{
                    borderColor: agentColor,
                    boxShadow: `0 0 15px ${agentColor}40`,
                }}
            >
                {/* Bubble Tail */}
                <div
                    className="absolute -bottom-2 left-1/2 transform -translate-x-1/2 w-4 h-4 rotate-45 border-r-2 border-b-2"
                    style={{
                        backgroundColor: '#1C1917',
                        borderColor: agentColor,
                    }}
                />

                {/* Thought Text */}
                <p className="text-[10px] text-stone-200 leading-tight font-medium">
                    {text}
                </p>
            </div>

            <style dangerouslySetInnerHTML={{__html: `
                @keyframes thoughtDrift {
                    0% {
                        transform: translateY(0) translateX(0);
                        opacity: 0;
                    }
                    10% {
                        opacity: 1;
                    }
                    90% {
                        opacity: 1;
                    }
                    100% {
                        transform: translateY(-120px) translateX(20px);
                        opacity: 0;
                    }
                }
            `}} />
        </div>
    );
};

export default ThoughtBubble;
