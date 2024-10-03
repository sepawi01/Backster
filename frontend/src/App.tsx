import {useState, useRef, useEffect} from "react";
import {HiArrowCircleUp} from "react-icons/hi";
import {useLocation} from 'react-router-dom';
import {BeatLoader} from 'react-spinners';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import SourcesModal from "./components/SourceModal.tsx";

function App() {
    const [inputValue, setInputValue] = useState("");
    const [messages, setMessages] = useState([
        {
            fromBot: true,
            text: "Hej! Jag heter Backster och är din assistent här på Backstage. Vilken anställningsform har du?"
        },

    ]);
    const [employmentType, setEmploymentType] = useState<string | null>(null);
    const [token, setToken] = useState("");
    const [isTyping, setIsTyping] = useState(false);
    const textareaRef = useRef<HTMLTextAreaElement | null>(null);
    const endOfMessagesRef = useRef<HTMLDivElement | null>(null);
    const [contents, setContents] = useState<string[]>([]);
    const [sources, setSources] = useState<string[]>([]);
    const [isModalOpen, setIsModalOpen] = useState(false);
    const location = useLocation();
    const queryParams = new URLSearchParams(location.search);
    const key = queryParams.get('key');
    const parkParam = queryParams.get('park') || 'glt';
    const parkMap: Record<string, string> = {
        'glt': 'Gröna Lund',
        'kdp': 'Kolmården',
        'fvp': 'Furuvik',
        'ssl': 'Skara Sommarland',
    }
    const park = parkMap[parkParam];
    const parkStyles: Record<string, string> = {
        'glt': 'bg-glt-primary-600 text-white',
        'kdp': 'bg-kdp-primary-600 text-white',
        'fvp': 'bg-fvp-primary-600 text-white',
        'ssl': 'bg-ssl-primary-600 text-white',
    }
    const parkStyle = parkStyles[parkParam];

    useEffect(() => {
        // Scrolla till botten när nya meddelanden läggs till
        if (endOfMessagesRef.current) {
            endOfMessagesRef.current.scrollIntoView({behavior: "smooth"});
        }
    }, [messages]);

    useEffect(() => {
        // Justera höjden på textarea när användaren skriver
        adjustTextAreaHeight();
    }, [inputValue]);

    useEffect(() => {

        const fetchToken = async () => {
                    try {
            const response = await fetch(`/?key=${key}`);
            if (!response.ok) {
                console.error("Failed to fetch root:", response.statusText);
                return;
            }
            const tokenFromHeader = response.headers.get('X-Token');
            if (tokenFromHeader) {
                setToken(tokenFromHeader);
            } else {
                console.error("Token not found in header");
            }
        } catch (error) {
            console.error("Error while getting token", error);
        }
    };
        fetchToken();
    }, []);
    const adjustTextAreaHeight = () => {
        const textarea = textareaRef.current;
        if (textarea) {
            textarea.style.height = "auto";
            textarea.style.height = textarea.scrollHeight + "px";
        }
    };

    const handleEmploymentTypeSelection = (type: string) => {
        setEmploymentType(type);
        setMessages((prevMessages) => [
            ...prevMessages,
            {fromBot: false, text: type},
            {fromBot: true, text: 'Tack, vad kan jag hjälpa dig med idag?'}
        ]);
    };

    const sendMessage = async () => {
        if (!inputValue.trim() || !token || employmentType === null) return;
        setInputValue("");
        setIsTyping(true);

        const newMessages = [...messages, {fromBot: false, text: inputValue}];
        setMessages(newMessages);

        try {
            const response = await fetch(`/chat?token=${token}`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    session_id: token,
                    query: inputValue,
                    park: park,
                    employmentType: employmentType
                }),
            });

            const data = await response.json();
            setMessages([...newMessages, {fromBot: true, text: data.text}]);
            setContents(data.contents);
            setSources(data.sources);
            console.log("Sources: ", data.sources);
            console.log("Contents: ", data.contents);
        } catch (error) {
            console.error("Fel vid kommunikation med backend:", error);
        } finally {
            setIsTyping(false);
        }
    };

    return (
        <div
            className="flex h-screen flex-col justify-between p-2 mx-auto w-full max-w-screen-md border rounded-2xl border-gray-200">
            <div className="flex justify-center">
                <img src="static/PRS_black_Sc_rgb.jpg" alt="PRS Logo" className="h-6 sm:h-8 m-1 sm:m-2"/>
            </div>

            {/* Chat area */}
            <div className="flex-grow overflow-y-auto p-2 sm:p-4">
                {messages.map((message, index) => (
                    <div key={index}
                         className={`my-1 sm:my-2 flex ${message.fromBot ? "justify-start" : "justify-end"}`}>
                        {message.fromBot && (
                            <img src="static/backster_head_new.png" alt="Bot Avatar"
                                 className="h-6 sm:h-10 rounded-full mr-2 sm:mr-3"/>
                        )}
                        <div
                            className={`inline-block p-2 sm:p-3 rounded-lg ${
                                message.fromBot ? parkStyle : "bg-gray-200 text-black"
                            }`}
                            style={{maxWidth: "80%"}}
                        >
                            {/* Render markdown-output */}
                            <div
                                className={`prose prose-sm sm:prose ${message.fromBot ? "prose-white" : "text-black"}`}>
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                    {message.text}
                                </ReactMarkdown>
                                {message.fromBot && index > 2 &&
                                    <hr className="my-2 sm:my-4 border-t border-gray-300"/>}
                                {message.fromBot && sources.length > 0 && index > 2 && (
                                    <button onClick={() => setIsModalOpen(true)}
                                            className="underline text-xs sm:text-sm prose-whiteText">
                                        Visa källor
                                    </button>
                                )}
                                {message.fromBot && index > 2 && (
                                    <p className="text-xs text-gray-200 font-semibold">Ai-genererat.</p>
                                )}
                            </div>
                        </div>
                    </div>
                ))}
                {/* Show buttons for employment type selection */}
                {employmentType === null && (
                    <div className="my-2 flex justify-end">
                         <div className="inline-block p-2 sm:p-3 rounded-lg bg-gray-200 text-black text-sm sm:text-base">
                            Välj anställningsform:
                            <div className="flex flex-col gap-1 sm:gap-2 p-1 sm:p-2">
                                <button
                                    className={`p-1 sm:p-2 rounded-lg bg-fvp-primary-400`}
                                    onClick={() => handleEmploymentTypeSelection('Tillsvidare')}
                                >
                                    Tillsvidare
                                </button>
                                <button
                                    className={`p-1 sm:p-2 rounded-lg bg-fvp-primary-400`}
                                    onClick={() => handleEmploymentTypeSelection('Säsong/Visstid')}
                                >
                                    Säsong/Visstid
                                </button>
                            </div>
                        </div>
                    </div>
                )}
                <div ref={endOfMessagesRef}/>
                {/* Show loading spinner when bot is typing */}
                {isTyping && (
                    <div className={"flex justify-start p-2 sm:p-4"}>
                        <BeatLoader size={10} color="#868585"/>
                    </div>
                )}
            </div>

            {/* Input area */}
            <div className="p-1 sm:p-2 m-2 bg-gray-100 rounded-3xl">
                <div className="flex items-center">
                    <textarea
                        disabled={employmentType === null}
                        ref={textareaRef}
                        className="flex-grow p-1 sm:p-2 mr-1 sm:mr-2 bg-gray-100 rounded-lg outline-none resize-none text-sm sm:text-base"
                        placeholder="Skriv din fråga här..."
                        value={inputValue}
                        onChange={(e) => setInputValue(e.target.value)}
                        rows={1}
                        style={{maxHeight: "450px", overflowY: "auto"}}
                        onKeyDown={(e) => {
                            if (e.key === 'Enter' && !e.shiftKey) {
                                e.preventDefault();
                                sendMessage();
                            }
                        }}
                    />
                    <HiArrowCircleUp size={"3em"} className="cursor-pointer text-gray-600"
                                     onClick={sendMessage}
                    />
                </div>
            </div>

            {/* Sources Modal */}
            {isModalOpen &&
                <SourcesModal
                    sources={sources}
                    contents={contents}
                    isOpen={isModalOpen}
                    onClose={() => setIsModalOpen(false)}
                />}
        </div>
    );
}

export default App;
