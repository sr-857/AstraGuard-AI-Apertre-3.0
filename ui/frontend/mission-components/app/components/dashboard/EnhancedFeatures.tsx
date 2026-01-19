'use client';

import { useState, useEffect } from 'react';

interface Alert {
  id: string;
  timestamp: string;
  type: 'warning' | 'critical' | 'info';
  message: string;
  satellite?: string;
}

interface Command {
  id: string;
  timestamp: string;
  satellite: string;
  command: string;
  status: 'pending' | 'success' | 'failed';
}

export const AlertFeed: React.FC = () => {
  const [alerts, setAlerts] = useState<Alert[]>([
    { id: '1', timestamp: new Date().toLocaleTimeString(), type: 'info', message: 'SAT-001 completed data dump', satellite: 'SAT-001' },
    { id: '2', timestamp: new Date().toLocaleTimeString(), type: 'warning', message: 'SAT-002 signal degraded to 67%', satellite: 'SAT-002' },
    { id: '3', timestamp: new Date().toLocaleTimeString(), type: 'critical', message: 'SAT-005 offline - troubleshooting initiated', satellite: 'SAT-005' },
  ]);

  useEffect(() => {
    const interval = setInterval(() => {
      const alertTypes = ['warning', 'critical', 'info'] as const;
      const satellites = ['SAT-001', 'SAT-002', 'SAT-003', 'SAT-004', 'SAT-006'];
      const messages = [
        'Signal strength adjusted',
        'Task completed successfully',
        'Latency spike detected',
        'Orbit corrected',
        'Status nominal',
      ];

      const newAlert: Alert = {
        id: Date.now().toString(),
        timestamp: new Date().toLocaleTimeString(),
        type: alertTypes[Math.floor(Math.random() * 3)],
        message: messages[Math.floor(Math.random() * messages.length)],
        satellite: satellites[Math.floor(Math.random() * satellites.length)],
      };

      setAlerts((prev) => [newAlert, ...prev.slice(0, 4)]);
    }, 15000);

    return () => clearInterval(interval);
  }, []);

  const getAlertColor = (type: Alert['type']) => {
    switch (type) {
      case 'critical':
        return 'border-red-500/50 bg-red-500/10 text-red-400';
      case 'warning':
        return 'border-yellow-500/50 bg-yellow-500/10 text-yellow-400';
      default:
        return 'border-cyan-500/50 bg-cyan-500/10 text-cyan-400';
    }
  };

  return (
    <div className="p-4 rounded-lg border border-cyan-500/30 bg-black/50">
      <h3 className="text-lg font-bold text-cyan-400 mb-4 glow-cyan">Alert Feed</h3>
      <div className="space-y-2 max-h-[300px] overflow-y-auto">
        {alerts.map((alert) => (
          <div
            key={alert.id}
            className={`p-3 rounded border text-sm font-mono ${getAlertColor(alert.type)}`}
          >
            <div className="flex justify-between items-start mb-1">
              <span className="font-bold">{alert.satellite || 'System'}</span>
              <span className="text-xs opacity-75">{alert.timestamp}</span>
            </div>
            <div className="text-xs opacity-90">{alert.message}</div>
          </div>
        ))}
      </div>
    </div>
  );
};

export const SystemHealth: React.FC = () => {
  const [cpu, setCpu] = useState(45);
  const [memory, setMemory] = useState(62);
  const [bandwidth, setBandwidth] = useState(78);

  useEffect(() => {
    const interval = setInterval(() => {
      setCpu((prev) => Math.max(20, Math.min(95, prev + (Math.random() - 0.5) * 10)));
      setMemory((prev) => Math.max(30, Math.min(90, prev + (Math.random() - 0.5) * 8)));
      setBandwidth((prev) => Math.max(40, Math.min(100, prev + (Math.random() - 0.5) * 12)));
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  const getHealthColor = (value: number) => {
    if (value > 80) return 'from-red-500 to-red-600';
    if (value > 60) return 'from-yellow-500 to-yellow-600';
    return 'from-cyan-500 to-cyan-600';
  };

  const MetricBar = ({ label, value }: { label: string; value: number }) => (
    <div className="mb-4">
      <div className="flex justify-between mb-2 text-sm">
        <span className="text-gray-400">{label}</span>
        <span className="text-cyan-400 font-bold">{Math.round(value)}%</span>
      </div>
      <div className="w-full bg-black/50 rounded-full h-3 border border-cyan-500/30 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 bg-gradient-to-r ${getHealthColor(value)} glow-cyan`}
          style={{ width: `${value}%` }}
        />
      </div>
    </div>
  );

  return (
    <div className="p-4 rounded-lg border border-cyan-500/30 bg-black/50">
      <h3 className="text-lg font-bold text-cyan-400 mb-4 glow-cyan">System Health</h3>
      <MetricBar label="CPU Load" value={cpu} />
      <MetricBar label="Memory" value={memory} />
      <MetricBar label="Bandwidth" value={bandwidth} />
    </div>
  );
};

export const CommandPanel: React.FC<{ selectedSat?: string }> = ({ selectedSat }) => {
  const [commands, setCommands] = useState<Command[]>([]);
  const [selectedCommand, setSelectedCommand] = useState('');

  const commandOptions = [
    'Status Check',
    'Data Dump',
    'Calibration',
    'Orbit Adjust',
    'Signal Boost',
    'System Reset',
  ];

  const sendCommand = () => {
    if (!selectedSat || !selectedCommand) return;

    const newCommand: Command = {
      id: Date.now().toString(),
      timestamp: new Date().toLocaleTimeString(),
      satellite: selectedSat,
      command: selectedCommand,
      status: 'pending',
    };

    setCommands((prev) => [newCommand, ...prev.slice(0, 3)]);
    setSelectedCommand('');

    // Simulate command execution
    setTimeout(() => {
      setCommands((prev) =>
        prev.map((cmd) =>
          cmd.id === newCommand.id ? { ...cmd, status: 'success' } : cmd
        )
      );
    }, 2000);
  };

  const getStatusColor = (status: Command['status']) => {
    switch (status) {
      case 'success':
        return 'text-green-400';
      case 'failed':
        return 'text-red-400';
      default:
        return 'text-yellow-400 animate-pulse';
    }
  };

  return (
    <div className="p-4 rounded-lg border border-cyan-500/30 bg-black/50">
      <h3 className="text-lg font-bold text-cyan-400 mb-4 glow-cyan">Command Panel</h3>

      {selectedSat ? (
        <div className="space-y-3">
          <div className="text-sm text-cyan-400 font-mono">Target: {selectedSat}</div>

          <select
            value={selectedCommand}
            onChange={(e) => setSelectedCommand(e.target.value)}
            className="w-full px-3 py-2 bg-black/50 border border-cyan-500/30 rounded text-cyan-400 focus:border-cyan-400 outline-none"
          >
            <option value="">Select command...</option>
            {commandOptions.map((cmd) => (
              <option key={cmd} value={cmd}>
                {cmd}
              </option>
            ))}
          </select>

          <button
            onClick={sendCommand}
            disabled={!selectedCommand}
            className="w-full px-4 py-2 bg-cyan-500/20 hover:bg-cyan-500/40 border border-cyan-500/50 rounded text-cyan-400 font-bold transition disabled:opacity-50 glow-cyan"
          >
            Send Command
          </button>

          <div className="mt-4 space-y-2 max-h-[200px] overflow-y-auto">
            {commands.map((cmd) => (
              <div key={cmd.id} className="p-2 bg-black/50 border border-gray-700 rounded text-sm">
                <div className="flex justify-between items-start">
                  <span className="text-gray-400">{cmd.command}</span>
                  <span className={`text-xs font-bold ${getStatusColor(cmd.status)}`}>
                    {cmd.status.toUpperCase()}
                  </span>
                </div>
                <div className="text-xs text-gray-500 mt-1">{cmd.timestamp}</div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="text-gray-500 text-sm text-center py-8">
          Select a satellite to send commands
        </div>
      )}
    </div>
  );
};
