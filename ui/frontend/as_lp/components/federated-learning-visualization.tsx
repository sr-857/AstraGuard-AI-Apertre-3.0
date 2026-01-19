/**
 * Federated Learning Visualization Component
 *
 * Interactive charts and graphs showing federated learning
 * performance, privacy metrics, and model convergence.
 */

'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  BarChart,
  Bar,
  ScatterChart,
  Scatter,
  Cell
} from 'recharts';
import { TrendingUp, Shield, Users, Activity, Eye, EyeOff } from 'lucide-react';

interface FederatedLearningVisualizationProps {
  metrics: any[];
  participants: string[];
  className?: string;
}

interface PrivacyMetrics {
  round: number;
  epsilon: number; // Privacy budget
  delta: number;  // Privacy loss probability
  noiseScale: number;
  utilityLoss: number;
}

interface ModelConvergenceData {
  round: number;
  localAccuracy: number;
  globalAccuracy: number;
  localLoss: number;
  globalLoss: number;
}

export function FederatedLearningVisualization({
  metrics,
  participants,
  className
}: FederatedLearningVisualizationProps) {
  const [selectedMetric, setSelectedMetric] = useState<'accuracy' | 'loss' | 'privacy'>('accuracy');
  const [showDetails, setShowDetails] = useState(false);

  // Generate mock data for visualization (in real app, this would come from API)
  const convergenceData: ModelConvergenceData[] = useMemo(() => {
    return Array.from({ length: 10 }, (_, i) => ({
      round: i + 1,
      localAccuracy: Math.min(0.95, 0.6 + i * 0.03 + Math.random() * 0.05),
      globalAccuracy: Math.min(0.92, 0.65 + i * 0.025 + Math.random() * 0.03),
      localLoss: Math.max(0.05, 0.4 - i * 0.035 + Math.random() * 0.02),
      globalLoss: Math.max(0.08, 0.35 - i * 0.028 + Math.random() * 0.015)
    }));
  }, []);

  const privacyData: PrivacyMetrics[] = useMemo(() => {
    return Array.from({ length: 10 }, (_, i) => ({
      round: i + 1,
      epsilon: 1.0 + i * 0.1,
      delta: Math.pow(10, -6 - i * 0.1),
      noiseScale: 0.1 + i * 0.02,
      utilityLoss: 0.02 + i * 0.005
    }));
  }, []);

  const participantActivity = useMemo(() => {
    return participants.map((participant, index) => ({
      name: `Node ${index + 1}`,
      contributions: Math.floor(Math.random() * 100) + 20,
      lastActive: new Date(Date.now() - Math.random() * 3600000).toLocaleTimeString(),
      status: Math.random() > 0.2 ? 'active' : 'idle'
    }));
  }, [participants]);

  const renderAccuracyChart = () => (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={convergenceData}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="round" />
        <YAxis domain={[0, 1]} />
        <Tooltip
          formatter={(value: number) => [`${(value * 100).toFixed(1)}%`, '']}
          labelFormatter={(label) => `Round ${label}`}
        />
        <Legend />
        <Line
          type="monotone"
          dataKey="localAccuracy"
          stroke="#3B82F6"
          strokeWidth={2}
          name="Local Accuracy"
          dot={{ fill: '#3B82F6', strokeWidth: 2, r: 4 }}
        />
        <Line
          type="monotone"
          dataKey="globalAccuracy"
          stroke="#10B981"
          strokeWidth={2}
          name="Global Accuracy"
          dot={{ fill: '#10B981', strokeWidth: 2, r: 4 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );

  const renderLossChart = () => (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={convergenceData}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="round" />
        <YAxis />
        <Tooltip
          formatter={(value: number) => [value.toFixed(4), '']}
          labelFormatter={(label) => `Round ${label}`}
        />
        <Legend />
        <Line
          type="monotone"
          dataKey="localLoss"
          stroke="#EF4444"
          strokeWidth={2}
          name="Local Loss"
          dot={{ fill: '#EF4444', strokeWidth: 2, r: 4 }}
        />
        <Line
          type="monotone"
          dataKey="globalLoss"
          stroke="#F59E0B"
          strokeWidth={2}
          name="Global Loss"
          dot={{ fill: '#F59E0B', strokeWidth: 2, r: 4 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );

  const renderPrivacyChart = () => (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={privacyData}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="round" />
        <YAxis yAxisId="left" orientation="left" />
        <YAxis yAxisId="right" orientation="right" />
        <Tooltip
          formatter={(value: number, name: string) => {
            if (name === 'epsilon') return [value.toFixed(2), 'Privacy Budget (ε)'];
            if (name === 'delta') return [value.toExponential(2), 'Privacy Loss (δ)'];
            if (name === 'noiseScale') return [value.toFixed(3), 'Noise Scale'];
            if (name === 'utilityLoss') return [`${(value * 100).toFixed(2)}%`, 'Utility Loss'];
            return [value, name];
          }}
          labelFormatter={(label) => `Round ${label}`}
        />
        <Legend />
        <Line
          yAxisId="left"
          type="monotone"
          dataKey="epsilon"
          stroke="#8B5CF6"
          strokeWidth={2}
          name="epsilon"
          dot={{ fill: '#8B5CF6', strokeWidth: 2, r: 4 }}
        />
        <Line
          yAxisId="right"
          type="monotone"
          dataKey="utilityLoss"
          stroke="#EC4899"
          strokeWidth={2}
          name="utilityLoss"
          dot={{ fill: '#EC4899', strokeWidth: 2, r: 4 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );

  const renderParticipantActivity = () => (
    <ResponsiveContainer width="100%" height={250}>
      <BarChart data={participantActivity}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="name" />
        <YAxis />
        <Tooltip
          formatter={(value: number) => [value, 'Contributions']}
          labelFormatter={(label) => `${label}`}
        />
        <Bar dataKey="contributions" fill="#3B82F6">
          {participantActivity.map((entry, index) => (
            <Cell
              key={`cell-${index}`}
              fill={entry.status === 'active' ? '#10B981' : '#6B7280'}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between"
      >
        <div className="flex items-center space-x-3">
          <TrendingUp className="h-6 w-6 text-blue-600" />
          <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
            Federated Learning Analytics
          </h2>
        </div>
        <button
          onClick={() => setShowDetails(!showDetails)}
          className="flex items-center space-x-2 px-3 py-1 text-sm bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
        >
          {showDetails ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          <span>{showDetails ? 'Hide' : 'Show'} Details</span>
        </button>
      </motion.div>

      {/* Metric Selector */}
      <div className="flex space-x-2">
        {[
          { key: 'accuracy', label: 'Model Accuracy', icon: TrendingUp },
          { key: 'loss', label: 'Training Loss', icon: Activity },
          { key: 'privacy', label: 'Privacy Metrics', icon: Shield }
        ].map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setSelectedMetric(key as any)}
            className={`flex items-center space-x-2 px-4 py-2 rounded-lg transition-colors ${
              selectedMetric === key
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
            }`}
          >
            <Icon className="h-4 w-4" />
            <span>{label}</span>
          </button>
        ))}
      </div>

      {/* Main Chart */}
      <motion.div
        key={selectedMetric}
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="bg-white dark:bg-gray-800 rounded-lg shadow p-6"
      >
        <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-4">
          {selectedMetric === 'accuracy' && 'Model Accuracy Convergence'}
          {selectedMetric === 'loss' && 'Training Loss Reduction'}
          {selectedMetric === 'privacy' && 'Privacy-Utility Trade-off'}
        </h3>

        {selectedMetric === 'accuracy' && renderAccuracyChart()}
        {selectedMetric === 'loss' && renderLossChart()}
        {selectedMetric === 'privacy' && renderPrivacyChart()}
      </motion.div>

      {/* Participant Activity */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="bg-white dark:bg-gray-800 rounded-lg shadow p-6"
      >
        <div className="flex items-center space-x-3 mb-4">
          <Users className="h-5 w-5 text-blue-600" />
          <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100">
            Participant Activity
          </h3>
        </div>

        {renderParticipantActivity()}

        <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
          <div className="flex items-center space-x-2">
            <div className="w-3 h-3 bg-green-500 rounded-full"></div>
            <span className="text-gray-600 dark:text-gray-400">Active Participants</span>
          </div>
          <div className="flex items-center space-x-2">
            <div className="w-3 h-3 bg-gray-400 rounded-full"></div>
            <span className="text-gray-600 dark:text-gray-400">Idle Participants</span>
          </div>
        </div>
      </motion.div>

      {/* Privacy Insights */}
      <AnimatePresence>
        {showDetails && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="bg-gradient-to-r from-green-50 to-blue-50 dark:from-green-900/20 dark:to-blue-900/20 rounded-lg p-6 border border-green-200 dark:border-green-800"
          >
            <div className="flex items-center space-x-3 mb-4">
              <Shield className="h-6 w-6 text-green-600" />
              <h3 className="text-lg font-medium text-green-800 dark:text-green-200">
                Privacy Protection Insights
              </h3>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <h4 className="font-medium text-gray-900 dark:text-gray-100 mb-2">
                  Differential Privacy
                </h4>
                <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
                  <li>• ε = {privacyData[privacyData.length - 1]?.epsilon.toFixed(2)} (Privacy Budget)</li>
                  <li>• δ = {privacyData[privacyData.length - 1]?.delta.toExponential(2)} (Privacy Loss)</li>
                  <li>• Noise added to model updates</li>
                  <li>• Utility loss: {(privacyData[privacyData.length - 1]?.utilityLoss * 100).toFixed(2)}%</li>
                </ul>
              </div>

              <div>
                <h4 className="font-medium text-gray-900 dark:text-gray-100 mb-2">
                  Security Measures
                </h4>
                <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
                  <li>• Model updates only (no raw data)</li>
                  <li>• Secure aggregation protocol</li>
                  <li>• Checksum validation</li>
                  <li>• Participant authentication</li>
                </ul>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}