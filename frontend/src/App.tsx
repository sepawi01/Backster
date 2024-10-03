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
            text: "Hej! Jag heter Backster och finns här för att hjälpa dig med dina arbetsrelaterade frågor." +
                " För att bättre kunna hjälpa dig med relevant information kring din anställning så undrar jag vilken anställningsform du har?"
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
        console.log("ParkParam: ", parkParam);
        console.log("Park: ", park);
        // Hämta JWT-token från backend när appen laddas
        const fetchToken = async () => {
            try {
                const response = await fetch(`/token?key=${key}`);
                if (!response.ok) {
                    console.error("Misslyckades att hämta token:", response.statusText);
                    return;
                }
                const data = await response.json();
                const token = data.token;
                if (token) {
                    setToken(token);
                } else {
                    console.error("Token hittades inte i svaret");
                }
            } catch (error) {
                console.error("Fel vid hämtning av token:", error);
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
                <img src="static/PRS_black_Sc_rgb.jpg" alt="PRS Logo" className="h-8 m-2"/>
            </div>

            {/* Chat area */}
            <div className="flex-grow overflow-y-auto p-4">
                {messages.map((message, index) => (
                    <div key={index} className={`my-2 flex ${message.fromBot ? "justify-start" : "justify-end"}`}>
                        {message.fromBot && (
                            <img src="static/backster_head_new.png" alt="Bot Avatar"
                                 className="h-10 rounded-full mr-3"/>
                        )}
                        <div
                            className={`inline-block p-3 rounded-lg ${
                                message.fromBot ? parkStyle : "bg-gray-200 text-black"
                            }`}
                            style={{maxWidth: "80%"}}
                        >
                            {/* Render markdown-output */}
                            <div className={`prose mb-2 ${message.fromBot ? "prose-white" : "text-black"}`}>
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                    {message.text}
                                </ReactMarkdown>
                                {message.fromBot && index > 2 && <hr className="my-4 border-t border-gray-300" />}
                                {message.fromBot && index > 2 && <p className="text-xs text-gray-500">Ai-genererat.</p>}
                                {message.fromBot  && sources.length > 0 && index > 2 && <a onClick={() => setIsModalOpen(true)}>Visa källor</a>}

                            </div>
                        </div>
                    </div>
                ))}
                {/* Show buttons for employment type selection */}
                {employmentType === null && (
                    <div className="my-2 flex justify-end">
                        <div className="inline-block p-3 rounded-lg bg-gray-200 text-black">
                            Välj anställningsform:
                            <div className="flex flex-col gap-2 p-2">
                                <button
                                    className={`mt-2 p-2 rounded-lg bg-glt-tertiary-300`}
                                    onClick={() => handleEmploymentTypeSelection('Tillsvidare')}
                                >
                                    Tillsvidare
                                </button>
                                <button
                                    className={`p-2 rounded-lg bg-glt-tertiary-300`}
                                    onClick={() => handleEmploymentTypeSelection('Säsong/Visstid')}
                                >
                                    Säsong/Visstidsanställd
                                </button>
                            </div>
                        </div>
                    </div>
                )}
                <div ref={endOfMessagesRef}/>
                {/* Show loading spinner when bot is typing */}
                {isTyping && (
                    <div className={"flex justify-start p-4"}>
                        <BeatLoader size={10} color="#868585"/>
                    </div>
                )}
            </div>

            {/* Input area */}
            <div className="p-2 m-3 bg-gray-100 rounded-3xl">
                <div className="flex items-center">
                    <textarea
                        disabled={employmentType === null}
                        ref={textareaRef}
                        className="flex-grow p-2 mr-2 bg-gray-100 rounded-lg outline-none resize-none"
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
            <SourcesModal
                sources={sources}
                contents={contents}
                isOpen={isModalOpen}
                onClose={() => setIsModalOpen(false)}
            />
        </div>
    );
}

export default App;
