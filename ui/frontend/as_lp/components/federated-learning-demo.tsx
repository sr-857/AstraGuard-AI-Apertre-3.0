/**
 * Federated Learning Demo Component
 *
 * Interactive demonstration of federated learning concepts
 * with simulated distributed training scenarios.
 */

'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Play,
  Pause,
  RotateCcw,
  Zap,
  Shield,
  Network,
  Database,
  TrendingUp,
  Users,
  Activity
} from 'lucide-react';

interface DemoNode {
  id: string;
  x: number;
  y: number;
  data: number[][];
  model: number[];
  isTraining: boolean;
  accuracy: number;
  privacyLevel: number;
}

interface DemoState {
  nodes: DemoNode[];
  globalModel: number[];
  round: number;
  isRunning: boolean;
  totalAccuracy: number;
}

const NODE_COUNT = 5;
const FEATURES_COUNT = 3;
const TRAINING_SAMPLES = 20;

export function FederatedLearningDemo() {
  const [demoState, setDemoState] = useState<DemoState>({
    nodes: [],
    globalModel: [],
    round: 0,
    isRunning: false,
    totalAccuracy: 0
  });

  const [selectedNode, setSelectedNode] = useState<string | null>(null);

  // Initialize demo
  const initializeDemo = useCallback(() => {
    const nodes: DemoNode[] = [];

    for (let i = 0; i < NODE_COUNT; i++) {
      // Generate synthetic data for each node (different distributions)
      const data = Array.from({ length: TRAINING_SAMPLES }, () => {
        const features = [
          8 + Math.random() * 4 + i * 0.5, // voltage (different baselines)
          20 + Math.random() * 20 + i * 2,  // temperature (different ranges)
          Math.random() * 2 - 1 + i * 0.1   // gyro (different biases)
        ];
        const anomaly = Math.random() > 0.8 ? 1 : 0; // 20% anomalies
        return [...features, anomaly];
      });

      nodes.push({
        id: `node-${i + 1}`,
        x: 100 + (i * 150) + Math.random() * 50,
        y: 150 + Math.random() * 100,
        data,
        model: [0.1, 0.2, 0.3, 0.4], // Initial weights
        isTraining: false,
        accuracy: 0,
        privacyLevel: 0.5 + Math.random() * 0.5
      });
    }

    setDemoState({
      nodes,
      globalModel: [0.1, 0.2, 0.3, 0.4], // Initial global model
      round: 0,
      isRunning: false,
      totalAccuracy: 0
    });
  }, []);

  // Simulate federated learning round
  const runFederatedRound = useCallback(() => {
    setDemoState(prev => {
      const newNodes = prev.nodes.map(node => ({
        ...node,
        isTraining: true
      }));

      // Simulate local training on each node
      setTimeout(() => {
        setDemoState(current => {
          const updatedNodes = current.nodes.map(node => {
            // Simulate training improvement
            const improvement = 0.05 + Math.random() * 0.1;
            const newAccuracy = Math.min(0.95, node.accuracy + improvement);

            // Update local model with some noise (simulating training)
            const newModel = node.model.map(w => w + (Math.random() - 0.5) * 0.1);

            return {
              ...node,
              model: newModel,
              accuracy: newAccuracy,
              isTraining: false
            };
          });

          // Aggregate models (federated averaging)
          const aggregatedModel = updatedNodes[0].model.map((_, i) =>
            updatedNodes.reduce((sum, node) => sum + node.model[i], 0) / updatedNodes.length
          );

          // Add differential privacy noise
          const noisyModel = aggregatedModel.map(w => w + (Math.random() - 0.5) * 0.05);

          // Update global model
          const totalAccuracy = updatedNodes.reduce((sum, node) => sum + node.accuracy, 0) / updatedNodes.length;

          return {
            ...current,
            nodes: updatedNodes,
            globalModel: noisyModel,
            round: current.round + 1,
            totalAccuracy,
            isRunning: current.round < 9 // Stop after 10 rounds
          };
        });
      }, 2000); // 2 second training simulation

      return {
        ...prev,
        nodes: newNodes
      };
    });
  }, []);

  const startDemo = () => {
    setDemoState(prev => ({ ...prev, isRunning: true }));
  };

  const stopDemo = () => {
    setDemoState(prev => ({ ...prev, isRunning: false }));
  };

  const resetDemo = () => {
    initializeDemo();
  };

  // Auto-run rounds when demo is running
  useEffect(() => {
    if (demoState.isRunning && demoState.round < 10) {
      const timer = setTimeout(runFederatedRound, 3000);
      return () => clearTimeout(timer);
    } else if (demoState.round >= 10) {
      setDemoState(prev => ({ ...prev, isRunning: false }));
    }
  }, [demoState.isRunning, demoState.round, runFederatedRound]);

  // Initialize on mount
  useEffect(() => {
    initializeDemo();
  }, [initializeDemo]);

  const selectedNodeData = selectedNode ? demoState.nodes.find(n => n.id === selectedNode) : null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-gradient-to-r from-purple-600 to-blue-600 rounded-lg p-6 text-white"
      >
        <div className="flex items-center space-x-3">
          <Network className="h-8 w-8" />
          <div>
            <h1 className="text-2xl font-bold">Federated Learning Demo</h1>
            <p className="text-purple-100">Watch distributed AI training in action</p>
          </div>
        </div>
      </motion.div>

      {/* Controls */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="bg-white dark:bg-gray-800 rounded-lg shadow p-6"
      >
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                {demoState.round}
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400">Rounds</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">
                {(demoState.totalAccuracy * 100).toFixed(1)}%
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400">Global Accuracy</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600">
                {demoState.nodes.filter(n => n.isTraining).length}
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400">Training Nodes</div>
            </div>
          </div>

          <div className="flex space-x-3">
            <button
              onClick={startDemo}
              disabled={demoState.isRunning || demoState.round >= 10}
              className="flex items-center space-x-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <Play className="h-4 w-4" />
              <span>Start Demo</span>
            </button>

            <button
              onClick={stopDemo}
              disabled={!demoState.isRunning}
              className="flex items-center space-x-2 px-4 py-2 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <Pause className="h-4 w-4" />
              <span>Stop</span>
            </button>

            <button
              onClick={resetDemo}
              className="flex items-center space-x-2 px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors"
            >
              <RotateCcw className="h-4 w-4" />
              <span>Reset</span>
            </button>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
          <motion.div
            className="bg-gradient-to-r from-purple-500 to-blue-500 h-2 rounded-full"
            initial={{ width: 0 }}
            animate={{ width: `${(demoState.round / 10) * 100}%` }}
            transition={{ duration: 0.5 }}
          />
        </div>
        <div className="text-center text-sm text-gray-600 dark:text-gray-400 mt-2">
          Round {demoState.round} of 10
        </div>
      </motion.div>

      {/* Network Visualization */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.2 }}
          className="lg:col-span-2 bg-white dark:bg-gray-800 rounded-lg shadow p-6"
        >
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
            Federated Network
          </h3>

          <div className="relative h-96 bg-gray-50 dark:bg-gray-900 rounded-lg overflow-hidden">
            {/* Central Coordinator */}
            <motion.div
              className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2"
              animate={{
                scale: demoState.isRunning ? [1, 1.1, 1] : 1,
                boxShadow: demoState.isRunning
                  ? ['0 0 0 0 rgba(139, 92, 246, 0.7)', '0 0 0 10px rgba(139, 92, 246, 0)', '0 0 0 0 rgba(139, 92, 246, 0)']
                  : '0 0 0 0 rgba(139, 92, 246, 0)'
              }}
              transition={{ duration: 2, repeat: demoState.isRunning ? Infinity : 0 }}
            >
              <div className="w-16 h-16 bg-purple-600 rounded-full flex items-center justify-center text-white font-bold shadow-lg">
                <Zap className="h-6 w-6" />
              </div>
              <div className="text-center text-xs mt-1 text-gray-600 dark:text-gray-400">
                Coordinator
              </div>
            </motion.div>

            {/* Nodes */}
            {demoState.nodes.map((node, index) => (
              <motion.div
                key={node.id}
                className="absolute cursor-pointer"
                style={{ left: node.x, top: node.y }}
                animate={{
                  scale: node.isTraining ? [1, 1.2, 1] : 1,
                  boxShadow: node.isTraining
                    ? ['0 0 0 0 rgba(16, 185, 129, 0.7)', '0 0 0 8px rgba(16, 185, 129, 0)', '0 0 0 0 rgba(16, 185, 129, 0)']
                    : '0 0 0 0 rgba(16, 185, 129, 0)'
                }}
                transition={{ duration: 1.5, repeat: node.isTraining ? Infinity : 0 }}
                onClick={() => setSelectedNode(node.id)}
              >
                <div className={`w-12 h-12 rounded-full flex items-center justify-center text-white font-bold shadow-lg transition-colors ${
                  node.isTraining
                    ? 'bg-yellow-500 animate-pulse'
                    : selectedNode === node.id
                    ? 'bg-blue-600'
                    : 'bg-green-500'
                }`}>
                  {index + 1}
                </div>
                <div className="text-center text-xs mt-1 text-gray-600 dark:text-gray-400">
                  {(node.accuracy * 100).toFixed(0)}%
                </div>
              </motion.div>
            ))}

            {/* Connection Lines */}
            <svg className="absolute inset-0 w-full h-full pointer-events-none">
              {demoState.nodes.map((node, index) => (
                <motion.line
                  key={`line-${index}`}
                  x1="50%"
                  y1="50%"
                  x2={`${(node.x / 600) * 100}%`}
                  y2={`${(node.y / 400) * 100}%`}
                  stroke={node.isTraining ? "#10B981" : "#6B7280"}
                  strokeWidth="2"
                  strokeDasharray={demoState.isRunning ? "5,5" : "none"}
                  animate={demoState.isRunning ? { strokeDashoffset: [0, -10] } : {}}
                  transition={{ duration: 1, repeat: demoState.isRunning ? Infinity : 0, ease: "linear" }}
                />
              ))}
            </svg>
          </div>

          {/* Legend */}
          <div className="flex justify-center space-x-6 mt-4 text-sm">
            <div className="flex items-center space-x-2">
              <div className="w-3 h-3 bg-green-500 rounded-full"></div>
              <span className="text-gray-600 dark:text-gray-400">Idle Node</span>
            </div>
            <div className="flex items-center space-x-2">
              <div className="w-3 h-3 bg-yellow-500 rounded-full animate-pulse"></div>
              <span className="text-gray-600 dark:text-gray-400">Training Node</span>
            </div>
            <div className="flex items-center space-x-2">
              <div className="w-3 h-3 bg-purple-600 rounded-full"></div>
              <span className="text-gray-600 dark:text-gray-400">Coordinator</span>
            </div>
          </div>
        </motion.div>

        {/* Node Details */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.3 }}
          className="bg-white dark:bg-gray-800 rounded-lg shadow p-6"
        >
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
            Node Details
          </h3>

          {selectedNodeData ? (
            <div className="space-y-4">
              <div className="text-center">
                <div className="text-3xl font-bold text-blue-600 mb-1">
                  {selectedNodeData.id.split('-')[1]}
                </div>
                <div className="text-sm text-gray-600 dark:text-gray-400">Node ID</div>
              </div>

              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-gray-600 dark:text-gray-400">Status</span>
                  <div className="flex items-center space-x-2">
                    <div className={`w-2 h-2 rounded-full ${
                      selectedNodeData.isTraining ? 'bg-yellow-500 animate-pulse' : 'bg-green-500'
                    }`}></div>
                    <span className="text-sm font-medium">
                      {selectedNodeData.isTraining ? 'Training' : 'Ready'}
                    </span>
                  </div>
                </div>

                <div className="flex justify-between items-center">
                  <span className="text-gray-600 dark:text-gray-400">Accuracy</span>
                  <span className="text-sm font-medium text-green-600">
                    {(selectedNodeData.accuracy * 100).toFixed(1)}%
                  </span>
                </div>

                <div className="flex justify-between items-center">
                  <span className="text-gray-600 dark:text-gray-400">Privacy Level</span>
                  <div className="flex items-center space-x-2">
                    <Shield className="h-4 w-4 text-blue-500" />
                    <span className="text-sm font-medium">
                      {(selectedNodeData.privacyLevel * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>

                <div className="flex justify-between items-center">
                  <span className="text-gray-600 dark:text-gray-400">Data Samples</span>
                  <div className="flex items-center space-x-2">
                    <Database className="h-4 w-4 text-purple-500" />
                    <span className="text-sm font-medium">
                      {selectedNodeData.data.length}
                    </span>
                  </div>
                </div>
              </div>

              {/* Model Weights Preview */}
              <div className="mt-4">
                <h4 className="text-sm font-medium text-gray-900 dark:text-gray-100 mb-2">
                  Model Weights
                </h4>
                <div className="bg-gray-50 dark:bg-gray-700 rounded p-2 text-xs font-mono">
                  {selectedNodeData.model.map((w, i) => (
                    <div key={i} className="flex justify-between">
                      <span>w{i}:</span>
                      <span>{w.toFixed(3)}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center py-12 text-gray-500 dark:text-gray-400">
              <Users className="h-12 w-12 mx-auto mb-2 opacity-50" />
              <p>Click on a node to view details</p>
            </div>
          )}
        </motion.div>
      </div>

      {/* Privacy Explanation */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
        className="bg-gradient-to-r from-green-50 to-blue-50 dark:from-green-900/20 dark:to-blue-900/20 rounded-lg p-6 border border-green-200 dark:border-green-800"
      >
        <div className="flex items-center space-x-3 mb-4">
          <Shield className="h-6 w-6 text-green-600" />
          <h3 className="text-lg font-medium text-green-800 dark:text-green-200">
            Privacy by Design
          </h3>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <div className="flex items-start space-x-2">
            <Database className="h-5 w-5 text-green-600 mt-0.5 flex-shrink-0" />
            <div>
              <div className="font-medium text-green-800 dark:text-green-200">Local Training</div>
              <div className="text-green-700 dark:text-green-300">Data never leaves your device</div>
            </div>
          </div>

          <div className="flex items-start space-x-2">
            <Activity className="h-5 w-5 text-blue-600 mt-0.5 flex-shrink-0" />
            <div>
              <div className="font-medium text-blue-800 dark:text-blue-200">Model Updates Only</div>
              <div className="text-blue-700 dark:text-blue-300">Share only model improvements</div>
            </div>
          </div>

          <div className="flex items-start space-x-2">
            <Shield className="h-5 w-5 text-purple-600 mt-0.5 flex-shrink-0" />
            <div>
              <div className="font-medium text-purple-800 dark:text-purple-200">Differential Privacy</div>
              <div className="text-purple-700 dark:text-purple-300">Add noise to protect individual data</div>
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  );
}