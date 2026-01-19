import React from 'react';

interface DesktopTabNavProps {
    activeTab: 'mission' | 'systems' | 'chaos' | 'uplink' | 'vault' | 'diagnostics';
    onTabChange: (tab: 'mission' | 'systems' | 'chaos' | 'uplink' | 'vault' | 'diagnostics') => void;
}

import { useSoundEffects } from '../../hooks/useSoundEffects';

export const DesktopTabNav: React.FC<DesktopTabNavProps> = ({ activeTab, onTabChange }) => {
    const { playClick } = useSoundEffects();

    const handleTabClick = (tabId: string) => {
        playClick();
        onTabChange(tabId as any);
    };
    return (
        <div className="hidden md:flex gap-2 pt-4">
            <button
                id="mission-tab"
                data-tab="mission"
                className={`px-6 py-3 rounded-t-lg font-mono text-lg font-semibold transition-all duration-300 ${activeTab === 'mission'
                    ? 'tab-active-teal bg-teal-500/10 border-b-2 border-teal-400 text-teal-300 glow-teal'
                    : 'text-gray-400 hover:text-teal-300 hover:bg-teal-500/5'
                    }`}
                onClick={() => onTabChange('mission')}
            >
                Mission
            </button>

            <button
                id="systems-tab"
                data-tab="systems"
                className={`ml-2 px-6 py-3 rounded-t-lg font-mono text-lg font-semibold transition-all duration-300 ${activeTab === 'systems'
                    ? 'tab-active-magenta bg-fuchsia-500/10 border-b-2 border-fuchsia-400 text-fuchsia-300 glow-magenta'
                    : 'text-gray-400 hover:text-fuchsia-300 hover:bg-fuchsia-500/5'
                    }`}
                onClick={() => onTabChange('systems')}
            >
                Systems
            </button>

            <button
                id="chaos-tab"
                data-tab="chaos"
                className={`ml-2 px-6 py-3 rounded-t-lg font-mono text-lg font-semibold transition-all duration-300 ${activeTab === 'chaos'
                    ? 'tab-active-amber bg-amber-500/10 border-b-2 border-amber-400 text-amber-300 glow-amber'
                    : 'text-gray-400 hover:text-amber-300 hover:bg-amber-500/5'
                    }`}
                onClick={() => onTabChange('chaos')}
            >
                Chaos
            </button>

            <button
                id="uplink-tab"
                data-tab="uplink"
                className={`ml-2 px-6 py-3 rounded-t-lg font-mono text-lg font-semibold transition-all duration-300 ${activeTab === 'uplink'
                    ? 'tab-active-green bg-green-500/10 border-b-2 border-green-400 text-green-300 glow-green'
                    : 'text-gray-400 hover:text-green-300 hover:bg-green-500/5'
                    }`}
                onClick={() => handleTabClick('uplink')}
            >
                Uplink
            </button>

            <button
                id="vault-tab"
                data-tab="vault"
                className={`ml-2 px-6 py-3 rounded-t-lg font-mono text-lg font-semibold transition-all duration-300 ${activeTab === 'vault'
                    ? 'tab-active-indigo bg-indigo-500/10 border-b-2 border-indigo-400 text-indigo-300 glow-indigo'
                    : 'text-gray-400 hover:text-indigo-300 hover:bg-indigo-500/5'
                    }`}
                onClick={() => handleTabClick('vault')}
            >
                Vault
            </button>
            <button
                id="diagnostics-tab"
                data-tab="diagnostics"
                className={`ml-2 px-6 py-3 rounded-t-lg font-mono text-lg font-semibold transition-all duration-300 ${activeTab === 'diagnostics'
                    ? 'tab-active-teal bg-cyan-500/10 border-b-2 border-cyan-400 text-cyan-300 glow-teal'
                    : 'text-gray-400 hover:text-cyan-300 hover:bg-cyan-500/5'
                    }`}
                onClick={() => handleTabClick('diagnostics')}
            >
                Diagnostics
            </button>
        </div>
    );
};
