import React, { useState, useEffect, useRef } from 'react';

interface CommandResponse {
    status: string;
    ack_id: string;
    message: string;
    timestamp: string;
}

import { useVoiceAssistant } from '../../hooks/useVoiceAssistant';
import { useSoundEffects } from '../../hooks/useSoundEffects';

export const CommandTerminal: React.FC = () => {
    const { playKeystroke, playSuccess } = useSoundEffects();
    const [history, setHistory] = useState<string[]>(['> ASTRAGUARD LINK ESTABLISHED', '> TYPE "HELP" FOR COMMANDS']);
    const [input, setInput] = useState('');
    const [isProcessing, setIsProcessing] = useState(false);
    const scrollRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);

    const { isListening, toggleListening, registerCommand, speak } = useVoiceAssistant({
        onCommand: (text) => {
            setInput(text);
            // Optionally auto-execute:
            // executeCommand(text);
        }
    });

    // Register Voice Commands on mount
    useEffect(() => {
        registerCommand("status", () => executeCommand("UPLINK --target SAT-ALPHA --cmd STATUS"), "Requesting status report.");
        registerCommand("scan", () => executeCommand("UPLINK --target PROBE-1 --cmd DIAGNOSTICS"), "Initiating system scan.");
        registerCommand("clear", () => setHistory(['> CONSOLE CLEARED']), "Terminal cleared.");
        registerCommand("help", () => executeCommand("HELP"), "Displaying available commands.");
    }, [registerCommand]);

    // Focus handling
    useEffect(() => {
        const handleFocus = () => inputRef.current?.focus();
        window.addEventListener('focus-terminal', handleFocus);
        return () => window.removeEventListener('focus-terminal', handleFocus);
    }, []);

    const handleInput = (e: React.ChangeEvent<HTMLInputElement>) => {
        setInput(e.target.value);
        playKeystroke();
    };

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [history]);

    const addToHistory = (line: string) => {
        setHistory(prev => [...prev, line]);
    };

    const executeCommand = async (rawCmd: string) => {
        const cmdParts = rawCmd.trim().split(/\s+/);
        const command = cmdParts[0].toUpperCase();

        // Client-side execution
        if (command === 'CLEAR') {
            setHistory(['> CONSOLE CLEARED']);
            speak("Terminal cleared.");
            return;
        }
        if (command === 'HELP') {
            addToHistory('AVAILABLE COMMANDS:');
            addToHistory('  UPLINK --target <ID> --cmd <ACTION>  Send command to satellite');
            addToHistory('  CLEAR                                Clear terminal');
            addToHistory('  HELP                                 Show this message');
            addToHistory('  EXAMPLES:');
            addToHistory('    uplink --target SAT-ALPHA --cmd REBOOT');
            addToHistory('    uplink --target PROBE-1 --cmd DIAGNOSTICS');
            speak("Here are the available commands.");
            return;
        }

        if (command === 'UPLINK') {
            // Parse arguments simpler: need --target and --cmd
            const targetIdx = cmdParts.indexOf('--target');
            const cmdArgIdx = cmdParts.indexOf('--cmd');

            if (targetIdx === -1 || cmdArgIdx === -1 || targetIdx + 1 >= cmdParts.length || cmdArgIdx + 1 >= cmdParts.length) {
                addToHistory("ERROR: Invalid syntax. Usage: uplink --target <ID> --cmd <ACTION>");
                speak("Invalid syntax.");
                return;
            }

            const target = cmdParts[targetIdx + 1];
            const action = cmdParts[cmdArgIdx + 1];

            setIsProcessing(true);
            addToHistory(`> ENCRYPTING PACKET FOR ${target}...`);
            speak(`Transmitting ${action} command to ${target}.`);

            try {
                const res = await fetch('http://localhost:8002/api/v1/uplink', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        target_id: target,
                        command: action
                    })
                });
                const data: CommandResponse = await res.json();

                addToHistory(`[${data.timestamp}] ACK:${data.ack_id} STATUS:${data.status.toUpperCase()}`);
                addToHistory(`> ${data.message}`);
                playSuccess();
                speak("Command executed successfully.");
            } catch (err) {
                addToHistory(`ERROR: Uplink failed - ${err}`);
                speak("Uplink failed.");
            } finally {
                setIsProcessing(false);
            }
        } else {
            addToHistory(`Unrecognized command: ${command}`);
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === 'Enter' && input.trim()) {
            const cmd = input;
            addToHistory(`user@astraguard:~$ ${cmd}`);
            setInput('');
            executeCommand(cmd);
        }
    };

    return (
        <div className="w-full h-full max-w-4xl mx-auto flex flex-col bg-black font-mono text-sm border border-slate-800 rounded-lg shadow-2xl overflow-hidden ring-1 ring-green-900/30 font-terminal p-4 min-h-[500px]">
            {/* Scan lines effect overlay */}
            <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(rgba(18,16,16,0)_50%,rgba(0,0,0,0.25)_50%),linear-gradient(90deg,rgba(255,0,0,0.06),rgba(0,255,0,0.02),rgba(0,0,255,0.06))] z-10 bg-[length:100%_2px,3px_100%] opacity-20"></div>

            {/* Header */}
            <div className="flex justify-between items-center mb-4 pb-2 border-b border-green-900/50 text-green-700">
                <span>SECURE UPLINK TERMINAL v4.2.0</span>
                <div className="flex items-center gap-4">
                    {isListening && <span className="text-red-500 animate-pulse font-bold tracking-widest">● LISTENING</span>}
                    {!isListening && <span className="animate-pulse">● CONNECTED</span>}
                </div>
            </div>

            {/* Terminal Output */}
            <div ref={scrollRef} className="flex-1 overflow-y-auto space-y-1 mb-4 scrollbar-thin scrollbar-thumb-green-900 scrollbar-track-transparent p-2">
                {history.map((line, i) => (
                    <div key={i} className={`${line.startsWith('ERROR') ? 'text-red-500' : 'text-green-500'} break-all`}>
                        {line}
                    </div>
                ))}
                {isProcessing && <div className="text-green-500 animate-pulse">_</div>}
            </div>

            {/* Input Line */}
            <div className="flex items-center gap-2 text-green-400 border-t border-green-900/30 pt-2 relative z-20">
                <span className="text-green-600 font-bold whitespace-nowrap">user@astraguard:~$</span>
                <input
                    ref={inputRef}
                    type="text"
                    value={input}
                    onChange={handleInput}
                    onKeyDown={handleKeyDown}
                    className="flex-1 bg-transparent border-none outline-none text-green-400 placeholder-green-900/50 font-bold caret-green-500"
                    autoFocus
                    placeholder={isListening ? "Listening..." : "Enter command..."}
                    spellCheck={false}
                />
                <button
                    onClick={toggleListening}
                    className={`p-2 rounded-full transition-all ${isListening ? 'bg-red-900/50 text-red-500 animate-pulse' : 'text-green-700 hover:text-green-400'}`}
                    title="Toggle Voice Command"
                >
                    {isListening ? '🎤' : '🎙️'}
                </button>
            </div>
        </div>
    );
};
