import { useState } from 'react';

interface SourcesModalProps {
    sources: string[];
    contents: string[];
    isOpen: boolean;
    onClose: () => void;
}

function SourcesModal({ sources, contents, isOpen, onClose }: SourcesModalProps) {
    const [currentIndex, setCurrentIndex] = useState(0);

    if (!isOpen) return null;

    const handleNext = () => {
        setCurrentIndex((prevIndex) => (prevIndex + 1) % sources.length);
    };

    const handlePrevious = () => {
        setCurrentIndex((prevIndex) => (prevIndex - 1 + sources.length) % sources.length);
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
            <div className="bg-white p-6 rounded-lg w-4/5 h-4/5 overflow-hidden">
                <h2 className="text-xl font-semibold mb-4">Källa {currentIndex + 1} av {sources.length}</h2>
                <div className="overflow-y-auto h-4/5 mb-4">
                    <h3 className="text-md font-semibold mb-2">{sources[currentIndex]}</h3>
                    <div dangerouslySetInnerHTML={{ __html: contents[currentIndex] }} />
                </div>
                <div className="flex justify-between">
                    <button onClick={handlePrevious} className="px-4 py-2 bg-gray-300 rounded">
                        Föregående
                    </button>
                    <button onClick={handleNext} className="px-4 py-2 bg-gray-300 rounded">
                        Nästa
                    </button>
                </div>
                <button onClick={onClose} className="mt-4 px-4 py-2 bg-red-400 rounded w-full">
                    Stäng
                </button>
            </div>
        </div>
    );
}

export default SourcesModal;
