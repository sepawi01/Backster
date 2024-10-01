import {useState, useRef, useEffect} from "react";
import {HiArrowCircleUp} from "react-icons/hi";
import { useLocation } from 'react-router-dom';


function App() {
    const [inputValue, setInputValue] = useState("");
    const [messages, setMessages] = useState([
        {
            fromBot: true,
            text: "Hej! Jag heter Backster och finns här för att hjälpa dig med dina arbetsrelaterade frågor. " +
                "Vad kan jag hjälpa dig med idag? 💫"
        },
    ]);
    const [token, setToken] = useState("");
    const textareaRef = useRef<HTMLTextAreaElement | null>(null);
    const location = useLocation();
    const queryParams = new URLSearchParams(location.search);
    const key = queryParams.get('key');
    const park = queryParams.get('park');


    useEffect(() => {
        adjustTextAreaHeight();
    }, [inputValue]);

    useEffect(() => {


        // Fetch the JWT token from the response headers when the app is loaded
        const fetchToken = async () => {

            try {
                const response = await fetch(`/token?key=${key}`);
                if (!response.ok) {
                    console.error("Failed to fetch token:", response.statusText);
                    return;
                }
                const data = await response.json(); // Parse the response to JSON
                const token = data.token; // Get the token from the parsed JSON
                if (token) {
                    setToken(token);
                } else {
                    console.error("Token not found in the response headers");
                }
            } catch (error) {
                console.error("Error fetching token:", error);
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

    const sendMessage = async () => {
        if (!inputValue.trim() || !token) return; // Ensure token is available

        const newMessages = [...messages, {fromBot: false, text: inputValue}];
        setMessages(newMessages);

        try {
            const response = await fetch(`/chat?token=${token}`, { // Send the token as a query parameter
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    session_id: token, // Use the token as the session ID
                    query: inputValue,
                    park: park,
                }),
            });

            const data = await response.json();
            setMessages([...newMessages, {fromBot: true, text: data.text}]);
        } catch (error) {
            console.error("Error communicating with the backend:", error);
        }

        setInputValue("");
    };

    return (
        <div
            className="flex h-screen flex-col justify-between p-2 mx-auto w-full max-w-screen-md border rounded-2xl border-gray-200">
            <div className="flex justify-center">
                <img src="static/PRS_black_Sc_rgb.jpg" alt="PRS Logo" className="h-8 m-2"/>
            </div>

            {/* Chat Area */}
            <div className="flex-grow overflow-y-auto p-4">
                {messages.map((message, index) => (
                    <div key={index} className={`my-2 flex ${message.fromBot ? "justify-start" : "justify-end"}`}>
                        {message.fromBot && (
                            <img src="static/backster_head_new.png" alt="Bot Avatar"
                                 className="h-10 rounded-full mr-3"/>
                        )}
                        <div
                            className={`inline-block p-3 rounded-lg ${
                                message.fromBot ? "bg-glt-primary-600 text-white" : "bg-gray-200 text-black"
                            }`}
                            style={{maxWidth: "80%"}}
                        >
                            {message.text.split("\n").map((line, idx) => (
                                <p key={idx} className="mb-1">{line}</p>
                            ))}
                        </div>
                    </div>
                ))}
            </div>

            {/* Input Area */}
            <div className="p-2 m-3 bg-gray-100 rounded-3xl">
                <div className="flex items-center">
                    <textarea
                        ref={textareaRef}
                        className="flex-grow p-2 mr-2 bg-gray-100 rounded-lg outline-none resize-none"
                        placeholder="Skriv din fråga här..."
                        value={inputValue}
                        onChange={(e) => setInputValue(e.target.value)}
                        rows={1}
                        style={{maxHeight: "450px", overflowY: "auto"}}
                    />
                    <HiArrowCircleUp size={"3em"} className="cursor-pointer text-gray-600"
                                     onClick={sendMessage}
                                     onKeyDown={(e) => {
                                         if (e.key === 'Enter' && !e.shiftKey) {
                                             e.preventDefault();
                                             sendMessage();
                                         }
                                     }}
                    />
                </div>
            </div>
        </div>
    );
}

export default App;
