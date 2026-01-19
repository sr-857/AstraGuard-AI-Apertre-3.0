import React, { useState } from 'react';

interface Props {
    activeTab: 'mission' | 'systems' | 'chaos' | 'uplink' | 'vault' | 'diagnostics';
    onTabChange: (tab: 'mission' | 'systems' | 'chaos' | 'uplink' | 'vault' | 'diagnostics') => void;
}

export const MobileNavHamburger: React.FC<Props> = ({ activeTab, onTabChange }) => {
    const [isOpen, setIsOpen] = useState(false);

    return (
        <div className="md:hidden w-full mb-4">
            {/* Mobile Header with Hamburger */}
            <div className="flex items-center justify-between p-4 bg-black/40 backdrop-blur-xl border border-teal-500/20 rounded-xl mb-2">
                <span className="text-teal-400 font-mono text-sm font-bold">MENU</span>
                <button
                    onClick={() => setIsOpen(!isOpen)}
                    className="p-2 text-teal-400 hover:bg-teal-500/10 rounded-lg transition-colors"
                    aria-label="Toggle menu"
                >
                    {isOpen ? (
                        <span className="text-xl">✕</span>
                    ) : (
                        <div className="space-y-1.5">
                            <div className="w-6 h-0.5 bg-teal-400"></div>
                            <div className="w-6 h-0.5 bg-teal-400"></div>
                            <div className="w-6 h-0.5 bg-teal-400"></div>
                        </div>
                    )}
                </button>
            </div>

            {/* Drawer / Vertical Stack */}
            <div className={`
        overflow-hidden transition-all duration-300 ease-out
        ${isOpen ? 'max-h-48 opacity-100' : 'max-h-0 opacity-0'}
      `}>
                <div className="flex flex-col space-y-2">
                    <button
                        data-mobile-tab="mission"
                        onClick={() => {
                            onTabChange('mission');
                            setIsOpen(false);
                        }}
                        className={`w-full text-left px-4 py-3 rounded-xl border flex items-center gap-3 transition-all font-mono font-bold ${activeTab === 'mission'
                            ? 'bg-teal-500/10 border-teal-500/50 text-teal-300 shadow-[0_0_20px_rgba(20,184,166,0.2)]'
                            : 'bg-black/40 border-white/10 text-gray-400'
                            }`}
                    >
                        🛰️ Mission
                    </button>
                    <button
                        data-mobile-tab="systems"
                        onClick={() => {
                            onTabChange('systems');
                            setIsOpen(false);
                        }}
                        className={`w-full text-left px-4 py-3 rounded-xl border flex items-center gap-3 transition-all font-mono font-bold ${activeTab === 'systems'
                            ? 'bg-fuchsia-500/10 border-fuchsia-500/50 text-fuchsia-300 shadow-[0_0_20px_rgba(217,70,239,0.2)]'
                            : 'bg-black/40 border-white/10 text-gray-400'
                            }`}
                    >
                        ⚙️ Systems
                    </button>
                    <button
                        data-mobile-tab="chaos"
                        onClick={() => {
                            onTabChange('chaos');
                            setIsOpen(false);
                        }}
                        className={`w-full text-left px-4 py-3 rounded-xl border flex items-center gap-3 transition-all font-mono font-bold ${activeTab === 'chaos'
                            ? 'bg-amber-500/10 border-amber-500/50 text-amber-300 shadow-[0_0_20px_rgba(245,158,11,0.2)]'
                            : 'bg-black/40 border-white/10 text-gray-400'
                            }`}
                    >
                        💥 Chaos
                    </button>
                    <button
                        data-mobile-tab="uplink"
                        onClick={() => {
                            onTabChange('uplink');
                            setIsOpen(false);
                        }}
                        className={`w-full text-left px-4 py-3 rounded-xl border flex items-center gap-3 transition-all font-mono font-bold ${activeTab === 'uplink'
                            ? 'bg-green-500/10 border-green-500/50 text-green-300 shadow-[0_0_20px_rgba(34,197,94,0.2)]'
                            : 'bg-black/40 border-white/10 text-gray-400'
                            }`}
                    >
                        📡 Uplink
                    </button>
                    <button
                        data-mobile-tab="vault"
                        onClick={() => {
                            onTabChange('vault');
                            setIsOpen(false);
                        }}
                        className={`w-full text-left px-4 py-3 rounded-xl border flex items-center gap-3 transition-all font-mono font-bold ${activeTab === 'vault'
                            ? 'bg-indigo-500/10 border-indigo-500/50 text-indigo-300 shadow-[0_0_20px_rgba(99,102,241,0.2)]'
                            : 'bg-black/40 border-white/10 text-gray-400'
                            }`}
                    >
                        🏆 Vault
                    </button>
                    <button
                        data-mobile-tab="diagnostics"
                        onClick={() => {
                            onTabChange('diagnostics');
                            setIsOpen(false);
                        }}
                        className={`w-full text-left px-4 py-3 rounded-xl border flex items-center gap-3 transition-all font-mono font-bold ${activeTab === 'diagnostics'
                            ? 'bg-cyan-500/10 border-cyan-500/50 text-cyan-300 shadow-[0_0_20px_rgba(6,182,212,0.2)]'
                            : 'bg-black/40 border-white/10 text-gray-400'
                            }`}
                    >
                        🔬 Diagnostics
                    </button>
                </div>
            </div>
        </div>
    );
};
