'use client';

import { Satellite } from '../../types/dashboard';

interface Props extends Satellite {
  onClick?: () => void;
  isSelected?: boolean;
}

export const SatelliteCard: React.FC<Props> = ({
  orbitSlot,
  status,
  latency,

  signalStrength,
  onClick,
  isSelected,
}) => {
  const statusConfig = {
    Nominal: {
      icon: '🟢',
      borderClass: 'border-cyan-500/30 hover:border-cyan-400',
      glowClass: 'glow-cyan',
      ringClass: 'ring-cyan-500/50',
      barClass: 'from-cyan-400 to-cyan-600',
    },
    Degraded: {
      icon: '🟡',
      borderClass: 'border-amber-500/30 hover:border-amber-400',
      glowClass: 'glow-amber',
      ringClass: 'ring-amber-500/50',
      barClass: 'from-amber-400 to-amber-600',
    },
    Critical: {
      icon: '🔴',
      borderClass: 'border-red-500/30 hover:border-red-400',
      glowClass: 'glow-red',
      ringClass: 'ring-red-500/50',
      barClass: 'from-red-400 to-red-600',
    },
  }[status];

  return (
    <div
      className={`
        p-4 rounded-xl border bg-black/40 backdrop-blur-md cursor-pointer
        group hover:scale-[1.02] hover:-translate-y-1 hover:shadow-xl
        transition-all duration-300 ease-out
        ${statusConfig.glowClass} ${statusConfig.borderClass}
        motion-safe:group-hover:[animation:lift-burst_0.6s_ease-out]
        ${isSelected ? `ring-2 ${statusConfig.ringClass} scale-[1.02]` : ''}
      `}
      onClick={onClick}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-mono opacity-75 hover-glitch transition-all duration-200">LEO-{orbitSlot}</span>
        <span className="text-xl">{statusConfig.icon}</span>
      </div>
      <div className="text-lg font-bold font-mono text-white mb-1 truncate">{status}</div>
      <div className="flex justify-between text-xs font-mono text-gray-400 mt-2">
        <div>Lat: {latency}ms</div>
        <div>Signal: {signalStrength}%</div>
      </div>

      {/* Signal Bar */}
      <div className="w-full bg-gray-800 h-1 mt-1 rounded-full overflow-hidden">
        <div
          className={`h-full ${status === 'Critical' ? 'bg-red-500' : 'bg-teal-500'}`}
          style={{ width: `${Math.min(signalStrength, 100)}%` }}
        />
      </div>
    </div>
  );
};
