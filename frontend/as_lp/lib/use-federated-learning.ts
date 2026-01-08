/**
 * React hooks for Federated Learning functionality
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  FederatedLearningClient,
  FederatedLearningConfig,
  FederatedModelUpdate,
  FederatedTrainingMetrics
} from './federated-learning-client';
import { useIntelligentApi } from './use-intelligent-api';

export interface FederatedLearningState {
  isConnected: boolean;
  isTraining: boolean;
  currentRound: number;
  metrics: FederatedTrainingMetrics | null;
  participants: string[];
  lastUpdate: Date | null;
  error: string | null;
}

export interface UseFederatedLearningOptions {
  config: FederatedLearningConfig;
  autoStart?: boolean;
  onModelUpdate?: (update: FederatedModelUpdate) => void;
  onTrainingComplete?: (metrics: FederatedTrainingMetrics) => void;
}

export function useFederatedLearning(options: UseFederatedLearningOptions) {
  const { config, autoStart = false, onModelUpdate, onTrainingComplete } = options;
  const api = useIntelligentApi();

  const [state, setState] = useState<FederatedLearningState>({
    isConnected: false,
    isTraining: false,
    currentRound: 0,
    metrics: null,
    participants: [],
    lastUpdate: null,
    error: null
  });

  const clientRef = useRef<FederatedLearningClient | null>(null);
  const trainingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Initialize federated learning client
  useEffect(() => {
    clientRef.current = new FederatedLearningClient(config);
    setState(prev => ({ ...prev, isConnected: true }));

    return () => {
      if (trainingIntervalRef.current) {
        clearInterval(trainingIntervalRef.current);
      }
    };
  }, [config]);

  // Auto-start training if enabled
  useEffect(() => {
    if (autoStart && clientRef.current && !state.isTraining) {
      startTraining();
    }
  }, [autoStart, state.isTraining]);

  const addTrainingSample = useCallback((features: number[]) => {
    if (clientRef.current) {
      clientRef.current.addTrainingSample(features);
    }
  }, []);

  const startTraining = useCallback(async () => {
    if (!clientRef.current || state.isTraining) return;

    setState(prev => ({ ...prev, isTraining: true, error: null }));

    try {
      // Train local model
      const metrics = await clientRef.current.trainLocalModel();

      // Generate model update
      const modelUpdate = clientRef.current.generateModelUpdate();

      // Send update to federation coordinator
      const response = await api.post('/api/federated-learning/update', modelUpdate);

      if (response.success) {
        setState(prev => ({
          ...prev,
          metrics,
          currentRound: metrics.roundsCompleted,
          lastUpdate: new Date(),
          participants: response.data.participants || prev.participants
        }));

        onModelUpdate?.(modelUpdate);
        onTrainingComplete?.(metrics);
      } else {
        throw new Error(response.error || 'Failed to submit model update');
      }
    } catch (error) {
      setState(prev => ({
        ...prev,
        error: error instanceof Error ? error.message : 'Training failed'
      }));
    } finally {
      setState(prev => ({ ...prev, isTraining: false }));
    }
  }, [api, state.isTraining, onModelUpdate, onTrainingComplete]);

  const stopTraining = useCallback(() => {
    if (trainingIntervalRef.current) {
      clearInterval(trainingIntervalRef.current);
      trainingIntervalRef.current = null;
    }
    setState(prev => ({ ...prev, isTraining: false }));
  }, []);

  const getGlobalModel = useCallback(async () => {
    try {
      const response = await api.get('/api/federated-learning/model');
      if (response.success && clientRef.current) {
        clientRef.current.updateGlobalModel(response.data.weights);
        setState(prev => ({ ...prev, lastUpdate: new Date() }));
      }
    } catch (error) {
      setState(prev => ({
        ...prev,
        error: error instanceof Error ? error.message : 'Failed to get global model'
      }));
    }
  }, [api]);

  const getFederationStatus = useCallback(async () => {
    try {
      const response = await api.get('/api/federated-learning/status');
      if (response.success) {
        setState(prev => ({
          ...prev,
          participants: response.data.participants || [],
          currentRound: response.data.currentRound || 0,
          lastUpdate: new Date()
        }));
      }
    } catch (error) {
      // Silently handle status check failures
      console.warn('Failed to get federation status:', error);
    }
  }, [api]);

  // Periodic status updates
  useEffect(() => {
    const interval = setInterval(getFederationStatus, 30000); // Every 30 seconds
    return () => clearInterval(interval);
  }, [getFederationStatus]);

  const resetClient = useCallback(() => {
    if (clientRef.current) {
      clientRef.current.clearTrainingData();
    }
    setState({
      isConnected: true,
      isTraining: false,
      currentRound: 0,
      metrics: null,
      participants: [],
      lastUpdate: null,
      error: null
    });
  }, []);

  return {
    state,
    actions: {
      addTrainingSample,
      startTraining,
      stopTraining,
      getGlobalModel,
      getFederationStatus,
      resetClient
    }
  };
}

export function useFederatedLearningMetrics() {
  const [metrics, setMetrics] = useState<FederatedTrainingMetrics[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const api = useIntelligentApi();

  const fetchMetrics = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await api.get('/api/federated-learning/metrics');
      if (response.success) {
        setMetrics(response.data.metrics || []);
      }
    } catch (error) {
      console.error('Failed to fetch federated learning metrics:', error);
    } finally {
      setIsLoading(false);
    }
  }, [api]);

  useEffect(() => {
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 60000); // Every minute
    return () => clearInterval(interval);
  }, [fetchMetrics]);

  return {
    metrics,
    isLoading,
    refetch: fetchMetrics
  };
}

export function useFederatedLearningParticipants() {
  const [participants, setParticipants] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const api = useIntelligentApi();

  const fetchParticipants = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await api.get('/api/federated-learning/participants');
      if (response.success) {
        setParticipants(response.data.participants || []);
      }
    } catch (error) {
      console.error('Failed to fetch participants:', error);
    } finally {
      setIsLoading(false);
    }
  }, [api]);

  useEffect(() => {
    fetchParticipants();
    const interval = setInterval(fetchParticipants, 30000); // Every 30 seconds
    return () => clearInterval(interval);
  }, [fetchParticipants]);

  return {
    participants,
    isLoading,
    refetch: fetchParticipants
  };
}