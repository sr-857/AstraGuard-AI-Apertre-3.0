'use client';

import React, { useState, useRef, useEffect } from 'react';
import { AIService } from '../../../services/ai-service';
import { useDashboard } from '../../context/DashboardContext';

export const CopilotChat: React.FC = () => {
    const [isOpen, setIsOpen] = useState(false);
    const [messages, setMessages] = useState<{ role: 'user' | 'assistant', content: string }[]>([
        { role: 'assistant', content: 'AstraGuard Copilot online. How can I assist with mission operations?' }
    ]);
    const [input, setInput] = useState('');
    const [isTyping, setIsTyping] = useState(false);
    const { state } = useDashboard();
    const scrollRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages, isTyping]);

    const handleSend = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!input.trim()) return;

        const userMsg = input.trim();
        setInput('');
        setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
        setIsTyping(true);

        const aiService = AIService.getInstance();
        const response = await aiService.getCopilotResponse(userMsg, state);

        setIsTyping(false);
        setMessages(prev => [...prev, { role: 'assistant', content: response }]);
    };

    return (
        <>
            {/* FAB */}
            <button
                onClick={() => setIsOpen(!isOpen)}
                className={`fixed bottom-24 right-6 w-14 h-14 rounded-full shadow-2xl z-50 flex items-center justify-center transition-all duration-300 ${isOpen ? 'bg-red-500 rotate-45' : 'bg-blue-600 hover:bg-blue-500 scale-110'
                    } group`}
            >
                <span className="text-2xl text-white group-hover:drop-shadow-[0_0_8px_rgba(255,255,255,0.8)]">
                    {isOpen ? '✕' : '🤖'}
                </span>
                {!isOpen && (
                    <span className="absolute -top-1 -right-1 flex h-4 w-4">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-4 w-4 bg-blue-500 border-2 border-slate-900"></span>
                    </span>
                )}
            </button>

            {/* Chat Window */}
            {isOpen && (
                <div className="fixed bottom-40 right-6 w-80 md:w-96 h-[500px] bg-slate-950 border border-slate-800 rounded-2xl shadow-2xl z-50 flex flex-col overflow-hidden animate-in slide-in-from-bottom-5 duration-300 ring-1 ring-white/10">
                    {/* Header */}
                    <div className="p-4 bg-slate-900 border-b border-slate-800 flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-blue-500/20 border border-blue-500/30 flex items-center justify-center">
                            <span className="text-lg">🤖</span>
                        </div>
                        <div>
                            <h3 className="text-sm font-bold text-white tracking-tight">AstraGuard Copilot</h3>
                            <div className="flex items-center gap-1.5">
                                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                                <span className="text-[10px] text-slate-400 uppercase tracking-widest font-semibold">Active Consciousness</span>
                            </div>
                        </div>
                    </div>

                    {/* Messages */}
                    <div
                        ref={scrollRef}
                        className="flex-1 overflow-y-auto p-4 space-y-4 scroll-smooth"
                    >
                        {messages.map((m, i) => (
                            <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                                <div className={`max-w-[85%] p-3 rounded-2xl text-xs leading-relaxed shadow-sm ${m.role === 'user'
                                        ? 'bg-blue-600 text-white rounded-tr-none border border-blue-500/50'
                                        : 'bg-slate-900 text-slate-200 rounded-tl-none border border-slate-800'
                                    }`}>
                                    {m.content}
                                </div>
                            </div>
                        ))}
                        {isTyping && (
                            <div className="flex justify-start">
                                <div className="bg-slate-900 text-slate-400 p-3 rounded-2xl rounded-tl-none border border-slate-800 flex gap-1">
                                    <span className="w-1.5 h-1.5 bg-slate-600 rounded-full animate-bounce"></span>
                                    <span className="w-1.5 h-1.5 bg-slate-600 rounded-full animate-bounce [animation-delay:0.2s]"></span>
                                    <span className="w-1.5 h-1.5 bg-slate-600 rounded-full animate-bounce [animation-delay:0.4s]"></span>
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Input */}
                    <form onSubmit={handleSend} className="p-4 bg-slate-900 border-t border-slate-800">
                        <div className="relative">
                            <input
                                type="text"
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                placeholder="Query mission status..."
                                className="w-full bg-slate-950 border border-slate-800 text-white text-xs p-3 pr-10 rounded-xl focus:outline-none focus:ring-1 focus:ring-blue-500/50 transition-all placeholder:text-slate-600"
                            />
                            <button
                                type="submit"
                                className="absolute right-2 top-1.5 p-1.5 text-blue-500 hover:text-blue-400 transition-colors"
                            >
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                                </svg>
                            </button>
                        </div>
                    </form>
                </div>
            )}
        </>
    );
};
