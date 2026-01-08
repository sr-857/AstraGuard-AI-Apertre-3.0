'use client';

import { createContext, useContext, ReactNode, useState, useEffect } from 'react';
import { TelemetryState, WSMessage } from '../types/websocket';
import { useDashboardWebSocket } from '../hooks/useDashboardWebSocket';

interface ContextValue {
    state: TelemetryState;
    isConnected: boolean;
    send: (msg: WSMessage) => void;
    dispatch: any;
    isReplayMode: boolean;
    toggleReplayMode: () => void;
    replayProgress: number;
    setReplayProgress: (p: any) => void;
    isPlaying: boolean;
    togglePlay: () => void;
    isBattleMode: boolean;
    setBattleMode: (active: boolean) => void;
}

const DashboardContext = createContext<ContextValue | undefined>(undefined);

export const DashboardProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    // TODO: Add error boundary for context provider failures
    // TODO: Implement state persistence caching for dashboard data
    const ws = useDashboardWebSocket();
    const [isBattleMode, setBattleMode] = useState(false);

    // Auto-trigger Battle Mode on Critical Anomalies
    useEffect(() => {
        if (ws.state.mission?.anomalies) {
            const hasCritical = ws.state.mission.anomalies.some((a: any) => a.severity === 'Critical');
            if (hasCritical && !isBattleMode) {
                setBattleMode(true);
            }
        }
    }, [ws.state.mission?.anomalies, isBattleMode]);

    const value = {
        ...ws,
        isBattleMode,
        setBattleMode
    };

    return (
        <DashboardContext.Provider value={value}>
            {children}
        </DashboardContext.Provider>
    );
};

export const useDashboard = () => {
    const context = useContext(DashboardContext);
    if (!context) throw new Error('useDashboard must be used within DashboardProvider');
    return context;
};
