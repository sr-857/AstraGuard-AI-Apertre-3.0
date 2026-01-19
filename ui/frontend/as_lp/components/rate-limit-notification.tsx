/**
 * Rate Limit Notification Component
 *
 * Provides user feedback during rate limiting and system degradation
 */

'use client';

import { useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { AlertTriangle, Clock, Wifi, WifiOff } from 'lucide-react';
import { useRateLimitNotifications, useSystemHealth } from '../lib/use-intelligent-api';

interface RateLimitNotificationProps {
  className?: string;
}

export function RateLimitNotification({ className = '' }: RateLimitNotificationProps) {
  const { notifications, removeNotification } = useRateLimitNotifications();
  const { health, getHealthStatusColor, getHealthStatusIcon } = useSystemHealth();

  return (
    <div className={`fixed top-4 right-4 z-50 space-y-2 ${className}`}>
      <AnimatePresence>
        {/* System Health Indicator */}
        {health && health.status !== 'healthy' && (
          <motion.div
            initial={{ opacity: 0, x: 300 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 300 }}
            className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg p-4 max-w-sm"
          >
            <div className="flex items-center space-x-3">
              <div className="flex-shrink-0">
                {health.status === 'critical' ? (
                  <WifiOff className="h-5 w-5 text-red-500" />
                ) : (
                  <Wifi className="h-5 w-5 text-yellow-500" />
                )}
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                  System Status: {health.status.charAt(0).toUpperCase() + health.status.slice(1)}
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  API requests may be slower due to high system load
                </p>
              </div>
              <div className="text-right">
                <div className={`text-lg ${getHealthStatusColor(health.status)}`}>
                  {getHealthStatusIcon(health.status)}
                </div>
              </div>
            </div>
          </motion.div>
        )}

        {/* Rate Limit Notifications */}
        {notifications.map((notification: typeof notifications[0]) => (
          <motion.div
            key={notification.id}
            initial={{ opacity: 0, x: 300 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 300 }}
            className={`bg-white dark:bg-gray-800 border rounded-lg shadow-lg p-4 max-w-sm ${
              notification.type === 'error'
                ? 'border-red-200 dark:border-red-800'
                : notification.type === 'warning'
                ? 'border-yellow-200 dark:border-yellow-800'
                : 'border-blue-200 dark:border-blue-800'
            }`}
          >
            <div className="flex items-start space-x-3">
              <div className="flex-shrink-0">
                {notification.type === 'error' ? (
                  <AlertTriangle className="h-5 w-5 text-red-500" />
                ) : notification.type === 'warning' ? (
                  <Clock className="h-5 w-5 text-yellow-500" />
                ) : (
                  <div className="h-5 w-5 rounded-full bg-blue-500 flex items-center justify-center">
                    <span className="text-xs text-white">i</span>
                  </div>
                )}
              </div>
              <div className="flex-1">
                <p className="text-sm text-gray-900 dark:text-gray-100">
                  {notification.message}
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  {new Date(notification.timestamp).toLocaleTimeString()}
                </p>
              </div>
              <button
                onClick={() => removeNotification(notification.id)}
                className="flex-shrink-0 ml-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
              >
                <span className="sr-only">Dismiss</span>
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}

// Loading indicator component
interface ApiLoadingIndicatorProps {
  loading: boolean;
  queueLength: number;
  className?: string;
}

export function ApiLoadingIndicator({ loading, queueLength, className = '' }: ApiLoadingIndicatorProps) {
  if (!loading && queueLength === 0) return null;

  return (
    <div className={`flex items-center space-x-2 text-sm text-gray-600 dark:text-gray-400 ${className}`}>
      {loading && (
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
          className="w-4 h-4 border-2 border-gray-300 border-t-gray-600 rounded-full"
        />
      )}
      <span>
        {loading ? 'Processing...' : queueLength > 0 ? `Queued: ${queueLength}` : ''}
      </span>
    </div>
  );
}

// Error display component
interface ApiErrorDisplayProps {
  error: string | null;
  rateLimited: boolean;
  retryAfter: number;
  onRetry?: () => void;
  className?: string;
}

export function ApiErrorDisplay({
  error,
  rateLimited,
  retryAfter,
  onRetry,
  className = ''
}: ApiErrorDisplayProps) {
  if (!error) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 ${className}`}
    >
      <div className="flex items-center space-x-3">
        <AlertTriangle className="h-5 w-5 text-red-500 flex-shrink-0" />
        <div className="flex-1">
          <p className="text-sm text-red-800 dark:text-red-200">{error}</p>
          {rateLimited && retryAfter > 0 && (
            <p className="text-xs text-red-600 dark:text-red-400 mt-1">
              Please wait {Math.ceil(retryAfter)} seconds before retrying.
            </p>
          )}
        </div>
        {onRetry && (
          <button
            onClick={onRetry}
            disabled={rateLimited && retryAfter > 0}
            className="px-3 py-1 text-xs bg-red-100 dark:bg-red-800 text-red-800 dark:text-red-200 rounded hover:bg-red-200 dark:hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {rateLimited && retryAfter > 0 ? `Retry in ${Math.ceil(retryAfter)}s` : 'Retry'}
          </button>
        )}
      </div>
    </motion.div>
  );
}