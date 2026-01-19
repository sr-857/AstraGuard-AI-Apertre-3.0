/**
 * Federated Learning Dashboard Component
 *
 * Main interface for managing federated learning participation
 * and monitoring training progress across distributed nodes.
 */

'use client';

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Brain,
  Users,
  Activity,
  Shield,
  Play,
  Pause,
  RotateCcw,
  TrendingUp,
  AlertTriangle,
  CheckCircle,
  Clock,
  Database
} from 'lucide-react';
import { useFederatedLearning, useFederatedLearningMetrics, useFederatedLearningParticipants } from '../lib/use-federated-learning';
import { FederatedLearningConfig } from '../lib/federated-learning-client';

interface FederatedLearningDashboardProps {
  className?: string;
}

const defaultConfig: FederatedLearningConfig = {
  nodeId: `node-${Date.now()}`,
  learningRate: 0.01,
  batchSize: 32,
  epochs: 10,
  privacyBudget: 1.0,
  aggregationRounds: 5,
  minNodesForAggregation: 3
};

export function FederatedLearningDashboard({ className }: FederatedLearningDashboardProps) {
  const [config, setConfig] = useState<FederatedLearningConfig>(defaultConfig);
  const [isConfigOpen, setIsConfigOpen] = useState(false);

  const { state, actions } = useFederatedLearning({
    config,
    autoStart: false
  });

  const { metrics, isLoading: metricsLoading } = useFederatedLearningMetrics();
  const { participants, isLoading: participantsLoading } = useFederatedLearningParticipants();

  const handleStartTraining = () => {
    actions.startTraining();
  };

  const handleStopTraining = () => {
    actions.stopTraining();
  };

  const handleReset = () => {
    actions.resetClient();
  };

  const handleConfigChange = (key: keyof FederatedLearningConfig, value: number) => {
    setConfig(prev => ({ ...prev, [key]: value }));
  };

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-gradient-to-r from-blue-600 to-purple-600 rounded-lg p-6 text-white"
      >
        <div className="flex items-center space-x-3">
          <Brain className="h-8 w-8" />
          <div>
            <h1 className="text-2xl font-bold">Federated Learning</h1>
            <p className="text-blue-100">Privacy-preserving distributed anomaly detection</p>
          </div>
        </div>
      </motion.div>

      {/* Status Overview */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatusCard
          title="Connection Status"
          value={state.isConnected ? "Connected" : "Disconnected"}
          icon={state.isConnected ? CheckCircle : AlertTriangle}
          color={state.isConnected ? "green" : "red"}
        />
        <StatusCard
          title="Training Status"
          value={state.isTraining ? "Active" : "Idle"}
          icon={state.isTraining ? Activity : Pause}
          color={state.isTraining ? "blue" : "gray"}
        />
        <StatusCard
          title="Current Round"
          value={state.currentRound.toString()}
          icon={RotateCcw}
          color="purple"
        />
        <StatusCard
          title="Participants"
          value={participants.length.toString()}
          icon={Users}
          color="indigo"
        />
      </div>

      {/* Control Panel */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6"
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
            Training Control
          </h2>
          <button
            onClick={() => setIsConfigOpen(!isConfigOpen)}
            className="px-4 py-2 text-sm bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
          >
            Configure
          </button>
        </div>

        {/* Configuration Panel */}
        <AnimatePresence>
          {isConfigOpen && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="mb-4 p-4 bg-gray-50 dark:bg-gray-700 rounded-lg"
            >
              <h3 className="text-lg font-medium mb-3">Training Configuration</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <ConfigInput
                  label="Learning Rate"
                  value={config.learningRate}
                  onChange={(value) => handleConfigChange('learningRate', value)}
                  min={0.001}
                  max={0.1}
                  step={0.001}
                />
                <ConfigInput
                  label="Batch Size"
                  value={config.batchSize}
                  onChange={(value) => handleConfigChange('batchSize', value)}
                  min={8}
                  max={128}
                  step={8}
                />
                <ConfigInput
                  label="Epochs"
                  value={config.epochs}
                  onChange={(value) => handleConfigChange('epochs', value)}
                  min={1}
                  max={50}
                  step={1}
                />
                <ConfigInput
                  label="Privacy Budget"
                  value={config.privacyBudget}
                  onChange={(value) => handleConfigChange('privacyBudget', value)}
                  min={0.1}
                  max={10}
                  step={0.1}
                />
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Control Buttons */}
        <div className="flex space-x-3">
          <button
            onClick={handleStartTraining}
            disabled={state.isTraining || !state.isConnected}
            className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Play className="h-4 w-4" />
            <span>Start Training</span>
          </button>

          <button
            onClick={handleStopTraining}
            disabled={!state.isTraining}
            className="flex items-center space-x-2 px-4 py-2 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Pause className="h-4 w-4" />
            <span>Stop Training</span>
          </button>

          <button
            onClick={handleReset}
            className="flex items-center space-x-2 px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors"
          >
            <RotateCcw className="h-4 w-4" />
            <span>Reset</span>
          </button>
        </div>

        {/* Error Display */}
        {state.error && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="mt-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg"
          >
            <div className="flex items-center space-x-2">
              <AlertTriangle className="h-5 w-5 text-red-500" />
              <span className="text-red-800 dark:text-red-200">{state.error}</span>
            </div>
          </motion.div>
        )}
      </motion.div>

      {/* Metrics Dashboard */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <TrainingMetrics metrics={state.metrics} isLoading={metricsLoading} />
        <ParticipantsList participants={participants} isLoading={participantsLoading} />
      </div>

      {/* Privacy Notice */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.4 }}
        className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4"
      >
        <div className="flex items-center space-x-3">
          <Shield className="h-6 w-6 text-green-600" />
          <div>
            <h3 className="text-lg font-medium text-green-800 dark:text-green-200">
              Privacy Protected
            </h3>
            <p className="text-green-700 dark:text-green-300">
              Your telemetry data never leaves your device. Only model updates with differential privacy are shared.
            </p>
          </div>
        </div>
      </motion.div>
    </div>
  );
}

// Helper Components
function StatusCard({
  title,
  value,
  icon: Icon,
  color
}: {
  title: string;
  value: string;
  icon: any;
  color: string;
}) {
  const colorClasses = {
    green: 'bg-green-500',
    red: 'bg-red-500',
    blue: 'bg-blue-500',
    gray: 'bg-gray-500',
    purple: 'bg-purple-500',
    indigo: 'bg-indigo-500'
  };

  return (
    <motion.div
      whileHover={{ scale: 1.02 }}
      className="bg-white dark:bg-gray-800 rounded-lg shadow p-4"
    >
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-600 dark:text-gray-400">{title}</p>
          <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">{value}</p>
        </div>
        <div className={`p-2 rounded-lg ${colorClasses[color as keyof typeof colorClasses]}`}>
          <Icon className="h-6 w-6 text-white" />
        </div>
      </div>
    </motion.div>
  );
}

function ConfigInput({
  label,
  value,
  onChange,
  min,
  max,
  step
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  min: number;
  max: number;
  step: number;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
        {label}
      </label>
      <input
        type="number"
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        min={min}
        max={max}
        step={step}
        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
      />
    </div>
  );
}

function TrainingMetrics({
  metrics,
  isLoading
}: {
  metrics: any;
  isLoading: boolean;
}) {
  if (isLoading) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-3/4 mb-4"></div>
          <div className="space-y-3">
            <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded"></div>
            <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-5/6"></div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: 0.3 }}
      className="bg-white dark:bg-gray-800 rounded-lg shadow p-6"
    >
      <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
        Training Metrics
      </h3>

      {metrics ? (
        <div className="space-y-4">
          <MetricItem
            label="Local Accuracy"
            value={`${(metrics.localAccuracy * 100).toFixed(1)}%`}
            icon={TrendingUp}
            color="green"
          />
          <MetricItem
            label="Local Loss"
            value={metrics.localLoss.toFixed(4)}
            icon={Activity}
            color="red"
          />
          <MetricItem
            label="Rounds Completed"
            value={metrics.roundsCompleted.toString()}
            icon={RotateCcw}
            color="blue"
          />
          <MetricItem
            label="Training Samples"
            value={metrics.totalSamples.toString()}
            icon={Database}
            color="purple"
          />
        </div>
      ) : (
        <div className="text-center py-8 text-gray-500 dark:text-gray-400">
          <Clock className="h-12 w-12 mx-auto mb-2 opacity-50" />
          <p>No training metrics available</p>
          <p className="text-sm">Start training to see metrics</p>
        </div>
      )}
    </motion.div>
  );
}

function MetricItem({
  label,
  value,
  icon: Icon,
  color
}: {
  label: string;
  value: string;
  icon: any;
  color: string;
}) {
  const colorClasses = {
    green: 'text-green-600',
    red: 'text-red-600',
    blue: 'text-blue-600',
    purple: 'text-purple-600'
  };

  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center space-x-3">
        <Icon className={`h-5 w-5 ${colorClasses[color as keyof typeof colorClasses]}`} />
        <span className="text-gray-700 dark:text-gray-300">{label}</span>
      </div>
      <span className="font-semibold text-gray-900 dark:text-gray-100">{value}</span>
    </div>
  );
}

function ParticipantsList({
  participants,
  isLoading
}: {
  participants: string[];
  isLoading: boolean;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: 0.3 }}
      className="bg-white dark:bg-gray-800 rounded-lg shadow p-6"
    >
      <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
        Federation Participants
      </h3>

      {isLoading ? (
        <div className="animate-pulse space-y-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-4 bg-gray-200 dark:bg-gray-700 rounded"></div>
          ))}
        </div>
      ) : participants.length > 0 ? (
        <div className="space-y-2">
          {participants.map((participant, index) => (
            <motion.div
              key={participant}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
              className="flex items-center space-x-3 p-3 bg-gray-50 dark:bg-gray-700 rounded-lg"
            >
              <div className="w-2 h-2 bg-green-500 rounded-full"></div>
              <span className="text-gray-700 dark:text-gray-300 font-mono text-sm">
                {participant}
              </span>
            </motion.div>
          ))}
        </div>
      ) : (
        <div className="text-center py-8 text-gray-500 dark:text-gray-400">
          <Users className="h-12 w-12 mx-auto mb-2 opacity-50" />
          <p>No participants found</p>
          <p className="text-sm">Waiting for federation to form</p>
        </div>
      )}
    </motion.div>
  );
}