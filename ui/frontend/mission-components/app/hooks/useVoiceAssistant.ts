import { useState, useEffect, useCallback, useRef } from 'react';

interface VoiceCommand {
    phrase: string;
    action: () => void;
    response: string;
}

interface UseVoiceAssistantProps {
    onCommand?: (text: string) => void;
}

export const useVoiceAssistant = ({ onCommand }: UseVoiceAssistantProps = {}) => {
    const [isListening, setIsListening] = useState(false);
    const [transcript, setTranscript] = useState('');
    const recognitionRef = useRef<any>(null);
    const commandsRef = useRef<VoiceCommand[]>([]);

    useEffect(() => {
        if (typeof window !== 'undefined') {
            const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
            if (SpeechRecognition) {
                const recognition = new SpeechRecognition();
                recognition.continuous = false;
                recognition.interimResults = false;
                recognition.lang = 'en-US';

                recognition.onstart = () => setIsListening(true);
                recognition.onend = () => setIsListening(false);

                recognition.onresult = (event: any) => {
                    const last = event.results.length - 1;
                    const text = event.results[last][0].transcript.toLowerCase().trim();
                    setTranscript(text);
                    if (onCommand) onCommand(text);
                    processCommand(text);
                };

                recognitionRef.current = recognition;
            }
        }
    }, [onCommand]);

    const registerCommand = useCallback((phrase: string, action: () => void, response: string) => {
        commandsRef.current.push({ phrase: phrase.toLowerCase(), action, response });
    }, []);

    const processCommand = (text: string) => {
        const command = commandsRef.current.find(c => text.includes(c.phrase));
        if (command) {
            command.action();
            speak(command.response);
        } else {
            // Optional: generic fallback
            // speak("Command not recognized.");
        }
    };

    const toggleListening = useCallback(() => {
        if (!recognitionRef.current) {
            alert("Speech recognition not supported in this browser.");
            return;
        }

        if (isListening) {
            recognitionRef.current.stop();
        } else {
            recognitionRef.current.start();
        }
    }, [isListening]);

    const speak = useCallback((text: string) => {
        if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
            const utterance = new SpeechSynthesisUtterance(text);
            // Try to find a robotic/sci-fi voice
            const voices = window.speechSynthesis.getVoices();
            const sciFiVoice = voices.find(v => v.name.includes('Google US English') || v.name.includes('Daniel'));
            if (sciFiVoice) utterance.voice = sciFiVoice;

            utterance.rate = 1.1;
            utterance.pitch = 0.9;
            window.speechSynthesis.speak(utterance);
        }
    }, []);

    return {
        isListening,
        transcript,
        toggleListening,
        registerCommand,
        speak
    };
};
