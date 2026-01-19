'use client';

import { useState, useEffect } from 'react';
import { KPI } from '../types/systems';

export const usePredictiveData = (kpis: KPI[]) => {
    const [predictiveKpis, setPredictiveKpis] = useState<KPI[]>(kpis);

    useEffect(() => {
        // Initialize risk history if not present
        const initialized = kpis.map(kpi => ({
            ...kpi,
            riskScore: kpi.riskScore ?? Math.floor(Math.random() * 30),
            riskHistory: kpi.riskHistory ?? Array.from({ length: 10 }, () => Math.floor(Math.random() * 30))
        }));
        setPredictiveKpis(initialized);

        const interval = setInterval(() => {
            setPredictiveKpis(prev => prev.map(kpi => {
                const voltatility = 5;
                const change = Math.floor(Math.random() * voltatility * 2) - voltatility;
                const newScore = Math.max(0, Math.min(100, (kpi.riskScore || 0) + change));
                const newHistory = [...(kpi.riskHistory || []).slice(1), newScore];

                return {
                    ...kpi,
                    riskScore: newScore,
                    riskHistory: newHistory
                };
            }));
        }, 5000);

        return () => clearInterval(interval);
    }, []);

    return predictiveKpis;
};
