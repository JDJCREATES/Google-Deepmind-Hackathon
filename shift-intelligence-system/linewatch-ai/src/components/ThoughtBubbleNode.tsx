import React from 'react';

interface ThoughtBubbleData {
    text: string;
    agentColor: string;
    isDragged: boolean;
    onClose: () => void;
}

const ThoughtBubbleNode: React.FC<{ data: ThoughtBubbleData }> = ({ data }) => {
    return (
        <div 
            className="pointer-events-auto cursor-move"
            style={{
                animation: data.isDragged ? 'none' : 'thoughtDrift 12s ease-out forwards',
            }}
        >
            <div 
                className="p-3 rounded-lg shadow-lg max-w-xs relative bg-opacity-90 backdrop-blur-sm"
                style={{ 
                    backgroundColor: (data.agentColor || '#6B7280') + '40', 
                    borderColor: data.agentColor || '#6B7280', 
                    borderWidth: '1px', 
                    borderStyle: 'solid' 
                }}
            >
                {/* Close button */}
                {/* Close button - Only visible when grabbed/dragged */}
                {data.isDragged && (
                    <button
                        onClick={(e) => {
                            e.stopPropagation();
                            data.onClose();
                        }}
                        className="absolute -top-2 -right-2 w-5 h-5 rounded-full bg-stone-700 hover:bg-stone-600 text-stone-300 hover:text-white flex items-center justify-center text-xs font-bold transition-colors shadow-md border border-stone-600"
                        style={{ cursor: 'pointer' }}
                    >
                        ×
                    </button>
                )}
                <p className="text-xs text-stone-200 leading-tight font-medium font-sans">
                    {data.text}
                </p>
            </div>
            <style dangerouslySetInnerHTML={{__html: `
                @keyframes thoughtDrift {
                    0% {
                        transform: translateY(0);
                        opacity: 0;
                    }
                    10% {
                        opacity: 1;
                    }
                    90% {
                        opacity: 1;
                    }
                    100% {
                        transform: translateY(-180px);
                        opacity: 0;
                    }
                }
            `}} />
        </div>
    );
};

export default ThoughtBubbleNode;
