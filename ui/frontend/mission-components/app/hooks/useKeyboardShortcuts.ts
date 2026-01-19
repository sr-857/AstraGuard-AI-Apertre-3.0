import { useEffect } from 'react';

interface ShortcutsProps {
    onTabChange: (tab: 'mission' | 'systems' | 'chaos' | 'uplink') => void;
    onTogglePlay: () => void;
    onOpenPalette: () => void;
    onFocusTerminal: () => void;
    isReplayMode: boolean;
}

export const useKeyboardShortcuts = ({
    onTabChange,
    onTogglePlay,
    onOpenPalette,
    onFocusTerminal,
    isReplayMode
}: ShortcutsProps) => {
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            // Ignore if in input/textarea (except Cmd+K)
            if (
                ['INPUT', 'TEXTAREA'].includes((e.target as HTMLElement).tagName) &&
                !(e.metaKey && e.key === 'k') && // Cmd+K
                !(e.ctrlKey && e.key === 'k') // Ctrl+K
            ) {
                return;
            }

            // Command Palette (Cmd+K or Ctrl+K)
            if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
                e.preventDefault();
                onOpenPalette();
                return;
            }

            // Tab Switching (1-4)
            if (!e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey) {
                switch (e.key) {
                    case '1':
                        onTabChange('mission');
                        break;
                    case '2':
                        onTabChange('systems');
                        break;
                    case '3':
                        onTabChange('chaos');
                        break;
                    case '4':
                        onTabChange('uplink');
                        break;
                    case ' ': // Space: Toggle Replay
                        if (isReplayMode) {
                            e.preventDefault();
                            onTogglePlay();
                        }
                        break;
                    case '/': // Slash: Focus Terminal
                        e.preventDefault();
                        onFocusTerminal();
                        break;
                }
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [onTabChange, onTogglePlay, onOpenPalette, onFocusTerminal, isReplayMode]);
};
