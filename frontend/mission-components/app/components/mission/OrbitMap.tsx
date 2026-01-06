'use client';

import { Satellite, AnomalyEvent } from '../../types/dashboard';

interface Props {
  satellites: Satellite[];
  selectedSat?: Satellite | null;
  onSatClick: (sat: Satellite) => void;
  anomalies: AnomalyEvent[];
}

export const OrbitMap: React.FC<Props> = ({ satellites, selectedSat, onSatClick, anomalies }) => {
  const getColorByStatus = (status: string) => {
    switch (status) {
      case 'Nominal':
        return { stroke: '#00f5ff', fill: '#00f5ff' };
      case 'Degraded':
        return { stroke: '#facc15', fill: '#facc15' };
      case 'Critical':
        return { stroke: '#ef4444', fill: '#ef4444' };
      default:
        return { stroke: '#00f5ff', fill: '#00f5ff' };
    }
  };

  return (
    <div className="relative w-full h-full rounded-2xl bg-black/50 backdrop-blur-xl border-2 border-teal-500/30 glow-teal p-4 flex items-center justify-center">
      <svg viewBox="0 0 800 600" className="w-full h-full max-h-96" preserveAspectRatio="xMidYMid meet">
        <defs>
          <radialGradient id="earthGrad" cx="50%" cy="50%">
            <stop offset="0%" stopColor="#1e3a8a" />
            <stop offset="50%" stopColor="#0f172a" />
            <stop offset="100%" stopColor="#020617" />
          </radialGradient>
          <filter id="glow">
            <feGaussianBlur stdDeviation="2.5" result="coloredBlur" />
            <feMerge>
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <style>{`
            @keyframes orbit { from { transform-origin: 400px 300px; transform: rotate(0deg); } to { transform-origin: 400px 300px; transform: rotate(360deg); } }
            @keyframes pulse-ring { 0% { r: 10; opacity: 0.8; } 50% { r: 14; opacity: 0.4; } 100% { r: 10; opacity: 0.8; } }
            .sat-icon { cursor: pointer; transition: all 0.3s ease; }
            .sat-icon:hover { filter: drop-shadow(0 0 8px #00f5ff); }
          `}</style>
        </defs>

        {/* Earth Gradient */}
        <circle
          cx="400"
          cy="300"
          r="140"
          fill="url(#earthGrad)"
          stroke="#00f5ff"
          strokeWidth="2"
          filter="url(#glow)"
        />

        {/* Tactical Radar Grid */}
        <g className="radar-grid opacity-30">
          {/* Crosshairs */}
          <line x1="0" y1="300" x2="800" y2="300" stroke="#00f5ff" strokeWidth="0.5" />
          <line x1="400" y1="0" x2="400" y2="600" stroke="#00f5ff" strokeWidth="0.5" />

          {/* Range Rings */}
          {[100, 200, 300, 400].map((r) => (
            <circle
              key={`range-${r}`}
              cx="400"
              cy="300"
              r={r}
              fill="none"
              stroke="#00f5ff"
              strokeWidth="0.5"
              opacity={r % 200 === 0 ? "0.3" : "0.1"}
            />
          ))}

          {/* Degree Ticks */}
          {[0, 45, 90, 135, 180, 225, 270, 315].map((deg) => (
            <line
              key={`tick-${deg}`}
              x1="400" y1="300"
              x2={400 + Math.cos(deg * Math.PI / 180) * 400}
              y2={300 + Math.sin(deg * Math.PI / 180) * 400}
              stroke="#00f5ff"
              strokeWidth="0.5"
              opacity="0.1"
            />
          ))}
        </g>

        {/* Satellites with Orbits */}
        {satellites.map((sat, idx) => {
          const baseAngle = (idx * (Math.PI * 2)) / satellites.length;
          const timeOffset = Date.now() * 0.0001 + idx;
          const angle = baseAngle + timeOffset;

          const orbitRadius = 220;
          const x = 400 + Math.cos(angle) * orbitRadius;
          const y = 300 + Math.sin(angle) * orbitRadius;

          const colors = getColorByStatus(sat.status);
          const isSelected = selectedSat?.id === sat.id;
          const radius = isSelected ? 7 : sat.status === 'Critical' ? 6 : 4;

          return (
            <g key={sat.id}>
              {/* Orbit Trail */}
              <circle
                cx="400"
                cy="300"
                r={orbitRadius}
                fill="none"
                stroke={colors.stroke}
                strokeWidth="1"
                opacity="0.15"
                strokeDasharray="3,3"
              />

              {/* Satellite Icon */}
              <g
                onClick={() => onSatClick(sat)}
                className="sat-icon"
              >
                <circle
                  cx={x}
                  cy={y}
                  r={radius}
                  fill={colors.fill}
                  opacity={isSelected ? 1 : 0.8}
                  filter="url(#glow)"
                >
                  <animate
                    attributeName="opacity"
                    values={isSelected ? '1;1;1' : '0.8;0.5;0.8'}
                    dur="2s"
                    repeatCount="indefinite"
                  />
                </circle>

                {/* Selection Ring */}
                {isSelected && (
                  <circle
                    cx={x}
                    cy={y}
                    r={radius + 3}
                    fill="none"
                    stroke={colors.stroke}
                    strokeWidth="2"
                    opacity="0.6"
                  >
                    <animate
                      attributeName="r"
                      values={`${radius + 3};${radius + 6};${radius + 3}`}
                      dur="1.5s"
                      repeatCount="indefinite"
                    />
                  </circle>
                )}
              </g>

              {/* Satellite Label */}
              <text
                x={x + 14}
                y={y + 4}
                fontSize="11"
                fill="#00f5ff"
                opacity="0.8"
                className="font-mono font-bold pointer-events-none tracking-wider"
              >
                LEO-{sat.orbitSlot}
              </text>
            </g>
          );
        })}

        {/* Anomaly Pins (Last 3) */}
        {anomalies.slice(0, 3).map((anomaly) => {
          const satIndex = satellites.findIndex((s) => s.orbitSlot === anomaly.satellite.split('-')[1]);
          if (satIndex === -1) return null;

          const baseAngle = (satIndex * (Math.PI * 2)) / satellites.length;
          const timeOffset = Date.now() * 0.0001 + satIndex;
          const angle = baseAngle + timeOffset;

          const orbitRadius = 220;
          const x = 400 + Math.cos(angle) * orbitRadius;
          const y = 300 + Math.sin(angle) * orbitRadius;

          const severityColor = anomaly.severity === 'Critical' ? '#ef4444' : anomaly.severity === 'Warning' ? '#facc15' : '#06b6d4';

          return (
            <g key={anomaly.id}>
              <circle
                cx={x}
                cy={y}
                r="10"
                fill="none"
                stroke={severityColor}
                strokeWidth="2"
                opacity="0.7"
                strokeDasharray="2,2"
              >
                <animate
                  attributeName="r"
                  values="10;14;10"
                  dur="2s"
                  repeatCount="indefinite"
                />
              </circle>
              <text
                x={x}
                y={y + 4}
                fontSize="9"
                fill={severityColor}
                textAnchor="middle"
                opacity="0.9"
                className="font-mono font-bold pointer-events-none"
              >
                !
              </text>
            </g>
          );
        })}
      </svg>

      {/* Legend */}
      <div className="absolute bottom-4 left-4 text-xs space-y-1">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-cyan-400" />
          <span className="text-cyan-400/80">Nominal</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-amber-400" />
          <span className="text-amber-400/80">Degraded</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-red-400" />
          <span className="text-red-400/80">Critical</span>
        </div>
      </div>
    </div>
  );
};
