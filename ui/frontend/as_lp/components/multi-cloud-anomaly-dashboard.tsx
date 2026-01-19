/**
 * Multi-Cloud Anomaly Detection Dashboard Component
 *
 * Unified interface for monitoring and responding to anomalies across multiple cloud platforms
 * (AWS, Azure, GCP) with provider-agnostic recovery strategies.
 */

'use client';

import React, { useState, useEffect, MouseEvent } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Cloud,
  AlertTriangle,
  CheckCircle,
  RefreshCw,
  Settings,
  Plus,
  X,
  Zap,
  Shield,
  Activity,
  Globe
} from 'lucide-react';

interface CloudProvider {
  id: string;
  name: string;
  icon: string;
  status: 'connected' | 'disconnected' | 'error';
  anomalies: number;
  lastSync: Date;
}

interface Anomaly {
  id: string;
  provider: string;
  type: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  description: string;
  timestamp: Date;
  status: 'active' | 'resolved' | 'recovering';
}

interface MultiCloudAnomalyDashboardProps {
  className?: string;
}

const cloudProviders: CloudProvider[] = [
  { id: 'aws', name: 'Amazon Web Services', icon: '☁️', status: 'connected', anomalies: 3, lastSync: new Date() },
  { id: 'azure', name: 'Microsoft Azure', icon: '🔷', status: 'connected', anomalies: 1, lastSync: new Date() },
  { id: 'gcp', name: 'Google Cloud Platform', icon: '🌐', status: 'disconnected', anomalies: 0, lastSync: new Date(Date.now() - 300000) },
];

const mockAnomalies: Anomaly[] = [
  {
    id: '1',
    provider: 'aws',
    type: 'High CPU Usage',
    severity: 'high',
    description: 'EC2 instance i-1234567890abcdef0 showing sustained high CPU utilization',
    timestamp: new Date(Date.now() - 300000),
    status: 'active'
  },
  {
    id: '2',
    provider: 'aws',
    type: 'Network Latency',
    severity: 'medium',
    description: 'Increased latency detected in us-east-1 region',
    timestamp: new Date(Date.now() - 600000),
    status: 'recovering'
  },
  {
    id: '3',
    provider: 'aws',
    type: 'Storage I/O',
    severity: 'low',
    description: 'EBS volume vol-1234567890abcdef0 experiencing high I/O wait',
    timestamp: new Date(Date.now() - 900000),
    status: 'resolved'
  },
  {
    id: '4',
    provider: 'azure',
    type: 'VM Performance',
    severity: 'critical',
    description: 'Azure VM experiencing memory pressure',
    timestamp: new Date(Date.now() - 120000),
    status: 'active'
  }
];

export function MultiCloudAnomalyDashboard({ className }: MultiCloudAnomalyDashboardProps) {
  const [selectedProviders, setSelectedProviders] = useState<string[]>(['aws', 'azure']);
  const [anomalies, setAnomalies] = useState<Anomaly[]>(mockAnomalies);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [showAddProvider, setShowAddProvider] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    // Simulate API call
    await new Promise(resolve => setTimeout(resolve, 2000));
    setIsRefreshing(false);
  };

  const handleRecovery = (anomalyId: string) => {
    setAnomalies((prev: Anomaly[]) => prev.map((anomaly: Anomaly) =>
      anomaly.id === anomalyId
        ? { ...anomaly, status: 'recovering' as const }
        : anomaly
    ));
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'text-red-600 bg-red-100';
      case 'high': return 'text-orange-600 bg-orange-100';
      case 'medium': return 'text-yellow-600 bg-yellow-100';
      case 'low': return 'text-green-600 bg-green-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'text-red-600';
      case 'recovering': return 'text-yellow-600';
      case 'resolved': return 'text-green-600';
      default: return 'text-gray-600';
    }
  };

  const filteredAnomalies = anomalies.filter((anomaly: Anomaly) =>
    selectedProviders.includes(anomaly.provider)
  );

  const totalAnomalies = filteredAnomalies.length;
  const criticalAnomalies = filteredAnomalies.filter((a: Anomaly) => a.severity === 'critical').length;
  const activeAnomalies = filteredAnomalies.filter((a: Anomaly) => a.status === 'active').length;

  return (
    <div className={`bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6 ${className}`}>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center space-x-3">
          {React.createElement(Globe, { className: "w-8 h-8 text-blue-600" })}
          <div>
            <h3 className="text-2xl font-bold text-gray-900 dark:text-white">
              Multi-Cloud Anomaly Detection
            </h3>
            <p className="text-gray-600 dark:text-gray-300">
              Monitor and recover from anomalies across cloud platforms
            </p>
          </div>
        </div>
        <div className="flex items-center space-x-2">
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => setShowAddProvider(!showAddProvider)}
            className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            {React.createElement(Plus, { className: "w-4 h-4" })}
            <span>Add Provider</span>
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="flex items-center space-x-2 px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </motion.button>
        </div>
      </div>

      {/* Cloud Provider Selection */}
      <div className="mb-6">
        <h4 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
          Connected Cloud Providers
        </h4>
        <div className="flex flex-wrap gap-3">
          {cloudProviders.map((provider: CloudProvider) => (
            <motion.div
              key={provider.id}
              whileHover={{ scale: 1.02 }}
              className={`flex items-center space-x-3 p-3 rounded-lg border-2 transition-all cursor-pointer ${selectedProviders.includes(provider.id)
                  ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                  : 'border-gray-200 dark:border-gray-700 hover:border-gray-300'
                }`}
              onClick={() => {
                setSelectedProviders((prev: string[]) =>
                  prev.includes(provider.id)
                    ? prev.filter((id: string) => id !== provider.id)
                    : [...prev, provider.id]
                );
              }}
            >
              <span className="text-2xl">{provider.icon}</span>
              <div>
                <div className="font-medium text-gray-900 dark:text-white">
                  {provider.name}
                </div>
                <div className="text-sm text-gray-600 dark:text-gray-300">
                  {provider.anomalies} anomalies • {provider.status}
                </div>
              </div>
              {selectedProviders.includes(provider.id) && (
                React.createElement(CheckCircle, { className: "w-5 h-5 text-blue-600" })
              )}
            </motion.div>
          ))}
        </div>
      </div>

      {/* Statistics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg">
          <div className="flex items-center space-x-2">
            {React.createElement(AlertTriangle, { className: "w-5 h-5 text-red-600" })}
            <span className="text-sm font-medium text-gray-900 dark:text-white">
              Total Anomalies
            </span>
          </div>
          <div className="text-2xl font-bold text-gray-900 dark:text-white mt-2">
            {totalAnomalies}
          </div>
        </div>
        <div className="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg">
          <div className="flex items-center space-x-2">
            {React.createElement(Zap, { className: "w-5 h-5 text-orange-600" })}
            <span className="text-sm font-medium text-gray-900 dark:text-white">
              Critical Issues
            </span>
          </div>
          <div className="text-2xl font-bold text-gray-900 dark:text-white mt-2">
            {criticalAnomalies}
          </div>
        </div>
        <div className="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg">
          <div className="flex items-center space-x-2">
            {React.createElement(Activity, { className: "w-5 h-5 text-yellow-600" })}
            <span className="text-sm font-medium text-gray-900 dark:text-white">
              Active Issues
            </span>
          </div>
          <div className="text-2xl font-bold text-gray-900 dark:text-white mt-2">
            {activeAnomalies}
          </div>
        </div>
      </div>

      {/* Anomalies List */}
      <div className="space-y-4">
        <h4 className="text-lg font-semibold text-gray-900 dark:text-white">
          Recent Anomalies
        </h4>
        <AnimatePresence>
          {filteredAnomalies.map((anomaly: Anomaly) => (
            <motion.div
              key={anomaly.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 hover:shadow-md transition-shadow"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center space-x-2 mb-2">
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${getSeverityColor(anomaly.severity)}`}>
                      {anomaly.severity.toUpperCase()}
                    </span>
                    <span className={`text-sm font-medium ${getStatusColor(anomaly.status)}`}>
                      {anomaly.status}
                    </span>
                    <span className="text-sm text-gray-600 dark:text-gray-300">
                      {cloudProviders.find(p => p.id === anomaly.provider)?.icon} {anomaly.provider.toUpperCase()}
                    </span>
                  </div>
                  <h5 className="font-medium text-gray-900 dark:text-white mb-1">
                    {anomaly.type}
                  </h5>
                  <p className="text-sm text-gray-600 dark:text-gray-300 mb-2">
                    {anomaly.description}
                  </p>
                  <div className="text-xs text-gray-500 dark:text-gray-400">
                    {mounted ? anomaly.timestamp.toLocaleString() : 'Loading time...'}
                  </div>
                </div>
                {anomaly.status === 'active' && (
                  <motion.button
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    onClick={() => handleRecovery(anomaly.id)}
                    className="flex items-center space-x-2 px-3 py-1 bg-green-600 text-white text-sm rounded hover:bg-green-700 transition-colors"
                  >
                    {React.createElement(Shield, { className: "w-4 h-4" })}
                    <span>Recover</span>
                  </motion.button>
                )}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
        {filteredAnomalies.length === 0 && (
          <div className="text-center py-8 text-gray-500 dark:text-gray-400">
            {React.createElement(CheckCircle, { className: "w-12 h-12 mx-auto mb-4 text-green-600" })}
            <p>No anomalies detected across selected providers</p>
          </div>
        )}
      </div>

      {/* Add Provider Modal */}
      <AnimatePresence>
        {showAddProvider && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
            onClick={() => setShowAddProvider(false)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-xl max-w-md w-full mx-4"
              onClick={(e: MouseEvent) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                  Add Cloud Provider
                </h3>
                <button
                  onClick={() => setShowAddProvider(false)}
                  className="text-gray-500 hover:text-gray-700"
                >
                  {React.createElement(X, { className: "w-6 h-6" })}
                </button>
              </div>
              <div className="space-y-3">
                {cloudProviders.filter((p: CloudProvider) => !selectedProviders.includes(p.id)).map((provider: CloudProvider) => (
                  <button
                    key={provider.id}
                    onClick={() => {
                      setSelectedProviders((prev: string[]) => [...prev, provider.id]);
                      setShowAddProvider(false);
                    }}
                    className="w-full flex items-center space-x-3 p-3 border border-gray-200 dark:border-gray-700 rounded-lg hover:border-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors"
                  >
                    <span className="text-2xl">{provider.icon}</span>
                    <div className="text-left">
                      <div className="font-medium text-gray-900 dark:text-white">
                        {provider.name}
                      </div>
                      <div className="text-sm text-gray-600 dark:text-gray-300">
                        {provider.anomalies} anomalies
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}