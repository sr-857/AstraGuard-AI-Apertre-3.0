import { useState, useEffect } from 'react';
import { FederatedLearningConfig } from './federated-learning-client';

export function useFederatedLearning(options: { config: FederatedLearningConfig; autoStart: boolean }) {
    const [state, setState] = useState({
        isConnected: false,
        isTraining: false,
        currentRound: 0,
        error: null as string | null,
        metrics: {
            localAccuracy: 0,
            localLoss: 0,
            roundsCompleted: 0,
            totalSamples: 0
        }
    });

    const actions = {
        startTraining: () => setState(prev => ({ ...prev, isTraining: true })),
        stopTraining: () => setState(prev => ({ ...prev, isTraining: false })),
        resetClient: () => setState(prev => ({ ...prev, isTraining: false, currentRound: 0, error: null }))
    };

    useEffect(() => {
        // Simulate connection
        const timer = setTimeout(() => {
            setState(prev => ({ ...prev, isConnected: true }));
        }, 1000);
        return () => clearTimeout(timer);
    }, []);

    return { state, actions };
}

export function useFederatedLearningMetrics() {
    const [metrics, setMetrics] = useState({
        localAccuracy: 0.85,
        localLoss: 0.15,
        roundsCompleted: 5,
        totalSamples: 1000
    });
    const [isLoading, setIsLoading] = useState(false);

    return { metrics, isLoading };
}

export function useFederatedLearningParticipants() {
    const [participants, setParticipants] = useState<string[]>([]);
    const [isLoading, setIsLoading] = useState(false);

    useEffect(() => {
        // Simulate loading participants
        setIsLoading(true);
        const timer = setTimeout(() => {
            setParticipants(['Node-A', 'Node-B', 'Node-C']);
            setIsLoading(false);
        }, 1500);
        return () => clearTimeout(timer);
    }, []);

    return { participants, isLoading };
}
