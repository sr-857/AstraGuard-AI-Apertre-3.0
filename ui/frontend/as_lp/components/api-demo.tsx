/**
 * API Demo Component
 *
 * Demonstrates intelligent API rate limiting and user feedback
 */

'use client';

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Play, Pause, RotateCcw, Activity } from 'lucide-react';
import { useIntelligentApi, useRateLimitNotifications } from '../lib/use-intelligent-api';
import { ApiLoadingIndicator, ApiErrorDisplay } from './rate-limit-notification';

export function ApiDemo() {
  const [isRunning, setIsRunning] = useState(false);
  const [requestCount, setRequestCount] = useState(0);
  const [intervalId, setIntervalId] = useState<NodeJS.Timeout | null>(null);

  const { addNotification } = useRateLimitNotifications();

  const {
    data,
    loading,
    error,
    rateLimited,
    systemHealth,
    queueLength,
    retryAfter,
    get,
  } = useIntelligentApi({
    priority: 2, // High priority for demo
    onRateLimit: () => {
      addNotification('Rate limit reached! Slowing down requests.', 'warning');
    },
    onSystemDegraded: (health) => {
      addNotification(`System health degraded: ${health.status}`, 'warning');
    },
  });

  const makeApiCall = async () => {
    try {
      // Simulate different types of API calls
      const endpoints = [
        '/health/ready', // Health check
        '/health/live',  // Liveness probe
        '/health/state', // System state
      ];

      const randomEndpoint = endpoints[Math.floor(Math.random() * endpoints.length)];
      await get(randomEndpoint);
      setRequestCount((prev: number) => prev + 1);
    } catch (err) {
      // Error is handled by the hook
    }
  };

  const startDemo = () => {
    setIsRunning(true);
    const id = setInterval(makeApiCall, 1000); // Make a request every second
    setIntervalId(id);
  };

  const stopDemo = () => {
    setIsRunning(false);
    if (intervalId) {
      clearInterval(intervalId);
      setIntervalId(null);
    }
  };

  const resetDemo = () => {
    stopDemo();
    setRequestCount(0);
  };

  // Cleanup on unmount
  React.useEffect(() => {
    return () => {
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [intervalId]);

  return (
    <section className="py-20 bg-gray-50 dark:bg-gray-900">
      <div className="container mx-auto px-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="max-w-4xl mx-auto"
        >
          <div className="text-center mb-12">
            <h2 className="text-3xl md:text-4xl font-bold text-gray-900 dark:text-white mb-4">
              Intelligent API Rate Limiting Demo
            </h2>
            <p className="text-lg text-gray-600 dark:text-gray-300">
              Experience adaptive rate limiting that adjusts based on system health and provides graceful user feedback.
            </p>
          </div>

          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-8">
            {/* Controls */}
            <div className="flex flex-wrap gap-4 mb-8 justify-center">
              <button
                onClick={isRunning ? stopDemo : startDemo}
                className={`flex items-center space-x-2 px-6 py-3 rounded-lg font-medium transition-colors ${
                  isRunning
                    ? 'bg-red-500 hover:bg-red-600 text-white'
                    : 'bg-blue-500 hover:bg-blue-600 text-white'
                }`}
              >
                {isRunning ? (
                  <>
                    <Pause className="w-5 h-5" />
                    <span>Stop Demo</span>
                  </>
                ) : (
                  <>
                    <Play className="w-5 h-5" />
                    <span>Start Demo</span>
                  </>
                )}
              </button>

              <button
                onClick={resetDemo}
                className="flex items-center space-x-2 px-6 py-3 bg-gray-500 hover:bg-gray-600 text-white rounded-lg font-medium transition-colors"
              >
                <RotateCcw className="w-5 h-5" />
                <span>Reset</span>
              </button>
            </div>

            {/* Status Display */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
              <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-6 text-center">
                <div className="text-3xl font-bold text-blue-600 dark:text-blue-400 mb-2">
                  {requestCount}
                </div>
                <div className="text-sm text-gray-600 dark:text-gray-300">
                  Total Requests
                </div>
              </div>

              <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-6 text-center">
                <div className="text-3xl font-bold text-green-600 dark:text-green-400 mb-2">
                  {queueLength}
                </div>
                <div className="text-sm text-gray-600 dark:text-gray-300">
                  Queued Requests
                </div>
              </div>

              <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-6 text-center">
                <div className={`text-3xl font-bold mb-2 ${
                  systemHealth?.status === 'healthy' ? 'text-green-600 dark:text-green-400' :
                  systemHealth?.status === 'degraded' ? 'text-yellow-600 dark:text-yellow-400' :
                  'text-red-600 dark:text-red-400'
                }`}>
                  <Activity className="w-8 h-8 mx-auto" />
                </div>
                <div className="text-sm text-gray-600 dark:text-gray-300">
                  System: {systemHealth?.status || 'Unknown'}
                </div>
              </div>
            </div>

            {/* Loading and Error States */}
            <div className="mb-6">
              <ApiLoadingIndicator
                loading={loading}
                queueLength={queueLength}
                className="justify-center"
              />
            </div>

            <ApiErrorDisplay
              error={error}
              rateLimited={rateLimited}
              retryAfter={retryAfter}
              onRetry={makeApiCall}
              className="mb-6"
            />

            {/* System Health Details */}
            {systemHealth && (
              <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-6">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                  System Health Metrics
                </h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div>
                    <div className="text-sm text-gray-600 dark:text-gray-300">CPU Usage</div>
                    <div className="text-lg font-semibold text-gray-900 dark:text-white">
                      {systemHealth.cpuUsage.toFixed(1)}%
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-gray-600 dark:text-gray-300">Memory Usage</div>
                    <div className="text-lg font-semibold text-gray-900 dark:text-white">
                      {systemHealth.memoryUsage.toFixed(1)}%
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-gray-600 dark:text-gray-300">Active Connections</div>
                    <div className="text-lg font-semibold text-gray-900 dark:text-white">
                      {systemHealth.activeConnections}
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-gray-600 dark:text-gray-300">Anomaly Score</div>
                    <div className="text-lg font-semibold text-gray-900 dark:text-white">
                      {(systemHealth.anomalyScore * 100).toFixed(1)}%
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Instructions */}
            <div className="mt-8 p-6 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
              <h3 className="text-lg font-semibold text-blue-900 dark:text-blue-100 mb-2">
                How It Works
              </h3>
              <ul className="text-sm text-blue-800 dark:text-blue-200 space-y-1">
                <li>• Click "Start Demo" to begin making API requests every second</li>
                <li>• The system automatically adjusts rate limits based on backend health</li>
                <li>• Watch notifications appear when rate limits are reached</li>
                <li>• System health metrics update in real-time</li>
                <li>• Requests are queued intelligently during high load</li>
              </ul>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}