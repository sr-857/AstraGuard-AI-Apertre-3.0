import React, { useState, useEffect, useRef } from 'react';

interface Props {
    isOpen: boolean;
    onClose: () => void;
    onNav: (tab: 'mission' | 'systems' | 'chaos' | 'uplink') => void;
}

export const CommandPalette: React.FC<Props> = ({ isOpen, onClose, onNav }) => {
    const [query, setQuery] = useState('');
    const [selectedIndex, setSelectedIndex] = useState(0);
    const inputRef = useRef<HTMLInputElement>(null);

    const commands = [
        { id: 'mission', label: 'Go to Mission Control', action: () => onNav('mission'), shortcut: '1' },
        { id: 'systems', label: 'Go to Systems Overview', action: () => onNav('systems'), shortcut: '2' },
        { id: 'chaos', label: 'Go to Chaos Engineering', action: () => onNav('chaos'), shortcut: '3' },
        { id: 'uplink', label: 'Go to Uplink Terminal', action: () => onNav('uplink'), shortcut: '4' },
    ];

    const filtered = commands.filter(c =>
        c.label.toLowerCase().includes(query.toLowerCase())
    );

    useEffect(() => {
        if (isOpen) {
            // Reset state when opening
            setQuery('');
            setSelectedIndex(0);
            setTimeout(() => inputRef.current?.focus(), 50);
        }
    }, [isOpen]);

    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (!isOpen) return;

            if (e.key === 'Escape') {
                onClose();
            } else if (e.key === 'ArrowDown') {
                e.preventDefault();
                setSelectedIndex(prev => (prev + 1) % filtered.length);
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                setSelectedIndex(prev => (prev - 1 + filtered.length) % filtered.length);
            } else if (e.key === 'Enter') {
                e.preventDefault();
                const cmd = filtered[selectedIndex];
                if (cmd) {
                    cmd.action();
                    onClose();
                }
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [isOpen, filtered, selectedIndex, onClose]);

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-start justify-center pt-[20vh] bg-black/60 backdrop-blur-sm animate-in fade-in duration-200" onClick={onClose}>
            <div
                className="w-full max-w-lg bg-black border border-slate-700/50 rounded-xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200"
                onClick={e => e.stopPropagation()}
            >
                <div className="flex items-center border-b border-slate-800 p-3">
                    <span className="text-slate-500 mr-3">🔍</span>
                    <input
                        ref={inputRef}
                        type="text"
                        className="flex-1 bg-transparent text-white placeholder-slate-500 outline-none h-6 font-mono text-sm"
                        placeholder="Type a command..."
                        value={query}
                        onChange={e => {
                            setQuery(e.target.value);
                            setSelectedIndex(0);
                        }}
                    />
                    <kbd className="hidden sm:inline-block px-2 py-0.5 text-[10px] font-mono text-slate-500 bg-slate-900 border border-slate-700 rounded-md">ESC</kbd>
                </div>

                <div className="max-h-[300px] overflow-y-auto p-2">
                    {filtered.map((cmd, index) => (
                        <button
                            key={cmd.id}
                            className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm font-mono transition-colors ${index === selectedIndex ? 'bg-indigo-600 text-white' : 'text-slate-300 hover:bg-slate-800'
                                }`}
                            onClick={() => {
                                cmd.action();
                                onClose();
                            }}
                            onMouseEnter={() => setSelectedIndex(index)}
                        >
                            <span>{cmd.label}</span>
                            {cmd.shortcut && (
                                <span className={`text-xs opacity-50 ${index === selectedIndex ? 'text-white' : 'text-slate-500'}`}>
                                    {cmd.shortcut}
                                </span>
                            )}
                        </button>
                    ))}
                    {filtered.length === 0 && (
                        <div className="p-4 text-center text-slate-500 font-mono text-sm">
                            No commands found.
                        </div>
                    )}
                </div>

                <div className="bg-slate-950 border-t border-slate-800 p-2 text-[10px] text-slate-600 font-mono flex gap-3 px-4">
                    <span>↑↓ to navigate</span>
                    <span>↵ to select</span>
                </div>
            </div>
        </div>
    );
};
