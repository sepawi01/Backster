import {useState} from 'react';

interface SourcesModalProps {
    sources: string[];
    contents: string[];
    isOpen: boolean;
    onClose: () => void;
}

function SourcesModal({sources, contents, isOpen, onClose}: SourcesModalProps) {
    const [currentIndex, setCurrentIndex] = useState(0);

    if (!isOpen) return null;

    const handleNext = () => {
        setCurrentIndex((prevIndex) => (prevIndex + 1) % sources.length);
    };

    const handlePrevious = () => {
        setCurrentIndex((prevIndex) => (prevIndex - 1 + sources.length) % sources.length);
    };

    return (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black bg-opacity-50 p-4">
            <div
                className="bg-white p-4 rounded-lg w-full max-w-lg h-full max-h-[80%] sm:max-w-2xl shadow-lg overflow-hidden">
                <h2 className="text-lg sm:text-xl font-semibold mb-4 text-center text-gray-800">Källa {currentIndex + 1} av {sources.length}</h2>
                <div className="overflow-y-auto max-h-[80%] sm:h-[80%] mb-4 p-3 border border-gray-300 rounded-lg bg-gray-50">
                    <h3 className="text-md sm:text-lg font-semibold mb-2 text-gray-700">{sources[currentIndex]}</h3>
                    <div className="text-sm sm:text-base text-gray-700"
                         dangerouslySetInnerHTML={{__html: contents[currentIndex]}}/>
                </div>
                <div className="flex justify-between p-2 my-2">
                    <div className="flex justify-start gap-2">
                        <button
                            onClick={handlePrevious}
                            className="px-2 sm:px-3 py-1 bg-gray-300 text-gray-800 rounded hover:bg-gray-400 transition duration-300"
                        >
                            Föregående
                        </button>
                        <button
                            onClick={handleNext}
                            className="px-2 sm:px-3 py-1 bg-gray-300 text-gray-800 rounded hover:bg-gray-400 transition duration-300"
                        >
                            Nästa
                        </button>
                    </div>
                    <div className="flex justify-end">
                        <button
                            onClick={onClose}
                            className="px-2 sm:px-3 py-1 bg-glt-tertiary-600 text-white rounded hover:bg-glt-tertiary-700 transition duration-300"
                        >
                            Stäng
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}

export default SourcesModal;
