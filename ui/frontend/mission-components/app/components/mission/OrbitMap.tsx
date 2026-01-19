import React, { useEffect, useState, useRef, useMemo } from 'react';
import dynamic from 'next/dynamic';
import { Satellite, AnomalyEvent } from '../../types/dashboard';
import { getSatellitePosition } from '../../utils/orbital';
import { useDashboard } from '../../context/DashboardContext';
import { useSoundscape } from '../../hooks/useSoundscape';

// Dynamically import Globe to avoid SSR issues with WebGL
const Globe = dynamic(() => import('react-globe.gl'), { ssr: false });

interface Props {
  satellites: Satellite[];
  selectedSat?: Satellite | null;
  onSatClick: (sat: Satellite) => void;
  anomalies: AnomalyEvent[];
}

export const OrbitMap: React.FC<Props> = ({ satellites, selectedSat, onSatClick, anomalies }) => {
  const globeEl = useRef<any>(null);
  const { groundStations, historicalAnomalies, dragPhysics } = useDashboard();
  const { setWhooshIntensity } = useSoundscape();
  const [points, setPoints] = useState<any[]>([]);
  const [arcs, setArcs] = useState<any[]>([]);
  const [showHeatmap, setShowHeatmap] = useState(false);

  // Calculate satellite positions (animation loop)
  useEffect(() => {
    const updatePositions = () => {
      const satPoints = satellites.map(getSatellitePosition);

      // Merge satellites with dynamic ground stations for point rendering
      const stationPoints = groundStations.map(gs => ({
        ...gs,
        alt: 0.01,
        type: 'STATION',
        status: gs.weather === 'Storm' ? 'INTERFERENCE' : 'ONLINE',
        color: gs.weather === 'Storm' ? '#f59e0b' : gs.weather === 'Rain' ? '#60a5fa' : '#06b6d4'
      }));

      // Calculate Links (Arcs) based on ground station connections
      const newArcs = groundStations.map(gs => {
        if (!gs.connectedSatelliteId) return null;

        const sat = satellites.find(s => s.id === gs.connectedSatelliteId);
        if (!sat) return null;

        const satPos = getSatellitePosition(sat);

        // Style based on weather
        const isBadWeather = gs.weather === 'Rain' || gs.weather === 'Storm';
        const beamColor = gs.weather === 'Storm' ? '#f59e0b' : gs.weather === 'Rain' ? '#3b82f6' : '#22c55e';

        return {
          startLat: satPos.lat,
          startLng: satPos.lng,
          endLat: gs.lat,
          endLng: gs.lng,
          color: [beamColor, beamColor],
          dashLength: isBadWeather ? 0.2 : 0.4,
          dashGap: isBadWeather ? 0.4 : 0.2,
          dashAnimateTime: isBadWeather ? 1000 : 2000,
          stroke: isBadWeather ? 0.2 : 0.4,
          weather: gs.weather
        };
      }).filter((a): a is NonNullable<typeof a> => a !== null);

      setPoints([...satPoints, ...stationPoints]);
      setArcs(newArcs);
    };

    const interval = setInterval(updatePositions, 50);
    return () => clearInterval(interval);
  }, [satellites, groundStations]);

  // Initial focus
  useEffect(() => {
    if (selectedSat && globeEl.current) {
      const pos = getSatellitePosition(selectedSat);
      globeEl.current.pointOfView({ lat: pos.lat, lng: pos.lng, altitude: 2 }, 1000);
    }
  }, [selectedSat]);

  // Auto-rotate and Audio Motion
  useEffect(() => {
    if (globeEl.current) {
      const controls = globeEl.current.controls();
      controls.autoRotate = !showHeatmap;
      controls.autoRotateSpeed = 0.5;

      // Detect user interaction speed for audio whoosh
      let lastAzimuth = controls.getAzimuthalAngle();
      const updateMotion = () => {
        const currentAzimuth = controls.getAzimuthalAngle();
        const delta = Math.abs(currentAzimuth - lastAzimuth);

        // If delta is high, it's user rotation
        if (delta > 0.001) {
          setWhooshIntensity(Math.min(delta * 10, 1));
        } else {
          setWhooshIntensity(0);
        }
        lastAzimuth = currentAzimuth;
      };

      const motionInterval = setInterval(updateMotion, 100);
      return () => clearInterval(motionInterval);
    }
  }, [showHeatmap, setWhooshIntensity]);

  const ringsData = useMemo(() => {
    // Anomaly Rings
    const anomalyRings = anomalies.map(anomaly => {
      const sat = satellites.find(s => s.orbitSlot === anomaly.satellite.split('-')[1]);
      if (!sat) return null;
      const pos = getSatellitePosition(sat);
      return {
        lat: pos.lat,
        lng: pos.lng,
        alt: pos.alt,
        maxR: 5,
        propagationSpeed: 5,
        repeatPeriod: 1000,
        color: '#ef4444'
      };
    }).filter((r): r is NonNullable<typeof r> => r !== null);

    // Ground Station Coverage Zones
    const stationRings = groundStations.map(gs => ({
      lat: gs.lat,
      lng: gs.lng,
      alt: 0,
      maxR: 8,
      propagationSpeed: gs.weather === 'Storm' ? 2 : 0.5,
      repeatPeriod: gs.weather === 'Storm' ? 500 : 2000,
      color: () => gs.weather === 'Storm' ? '#f59e0b' : '#06b6d4'
    }));

    // Heat Veil (Atmospheric Drag)
    const heatRings = (() => {
      if (!dragPhysics || dragPhysics.altitude > 400) return [];

      const sat = satellites[0]; // Assume first satellite is main for now
      if (!sat) return [];
      const pos = getSatellitePosition(sat);

      // Intensity based on altitude (lower = more intense)
      const intensity = Math.max(0, (400 - dragPhysics.altitude) / 200); // 0 to 1

      return [{
        lat: pos.lat,
        lng: pos.lng,
        alt: pos.alt,
        maxR: 15 * intensity,
        propagationSpeed: 20 * intensity,
        repeatPeriod: 200, // Fast shimmer
        color: (t: any) => `rgba(255, ${Math.round(100 - (intensity * 100))}, 0, ${1 - t})` // Orange/Red fade
      }];
    })();

    return [...anomalyRings, ...stationRings, ...heatRings];
  }, [anomalies, satellites, groundStations, dragPhysics]);

  const weatherEmoji = (status: string) => {
    switch (status) {
      case 'Rain': return '🌧️';
      case 'Storm': return '⚡';
      case 'Clouds': return '☁️';
      default: return '☀️';
    }
  };

  return (
    <div className="relative w-full h-full bg-slate-950 rounded-sm border border-slate-900 overflow-hidden flex items-center justify-center">
      <Globe
        ref={globeEl}
        width={800}
        height={500}
        globeImageUrl="//unpkg.com/three-globe/example/img/earth-blue-marble.jpg"
        bumpImageUrl="//unpkg.com/three-globe/example/img/earth-topology.png"
        backgroundImageUrl="//unpkg.com/three-globe/example/img/night-sky.png"

        atmosphereColor={showHeatmap ? "#ef4444" : "#3b82f6"}
        atmosphereAltitude={0.15}

        pointsData={showHeatmap ? [] : points}
        pointAltitude="alt"
        pointColor="color"
        pointRadius={(d: any) => d.type === 'STATION' ? 0.8 : 0.5}
        pointLabel={(d: any) => `
            <div style="background: rgba(15, 23, 42, 0.9); padding: 12px; border: 1px solid ${d.type === 'STATION' ? d.color : '#334155'}; border-radius: 8px; color: white; backdrop-filter: blur(8px); box-shadow: 0 4px 20px rgba(0,0,0,0.5);">
                <div style="font-weight: bold; color: ${d.color}; font-size: 14px; margin-bottom: 4px;">
                    ${d.type === 'STATION' ? weatherEmoji(d.weather) : ''} ${d.name}
                </div>
                <div style="font-size: 11px; opacity: 0.8;">${d.type === 'STATION' ? 'GROUND_UPLINK' : 'AS_CORE_v2.4'}</div>
                <div style="display: flex; align-items: center; gap: 8px; margin-top: 8px;">
                  <span style="width: 8px; height: 8px; border-radius: 50%; background: ${d.color}; display: inline-block;"></span>
                  <span style="font-size: 12px; font-weight: bold;">${d.status}</span>
                </div>
                ${d.type === 'STATION' ? `<div style="font-size: 10px; margin-top: 4px; color: #94a3b8;">WEATHER: ${d.weather.toUpperCase()}</div>` : ''}
            </div>
        `}
        onPointClick={(point: any) => {
          if (point.type !== 'STATION') {
            const originalSat = satellites.find(s => s.id === point.id);
            if (originalSat) onSatClick(originalSat);
          }
        }}

        arcsData={showHeatmap ? [] : arcs}
        arcColor={(d: any) => d.color}
        arcDashLength={(d: any) => d.dashLength}
        arcDashGap={(d: any) => d.dashGap}
        arcDashAnimateTime={(d: any) => d.dashAnimateTime}
        arcStroke={(d: any) => d.stroke}
        arcAltitudeAutoScale={0.2}

        ringsData={showHeatmap ? [] : ringsData}
        ringColor={(d: any) => d.color}
        ringMaxRadius="maxR"
        ringPropagationSpeed="propagationSpeed"
        ringRepeatPeriod="repeatPeriod"

        labelsData={showHeatmap ? [] : groundStations}
        labelLat="lat"
        labelLng="lng"
        labelText="name"
        labelSize={1}
        labelDotRadius={0.4}
        labelColor={(d: any) => d.weather === 'Storm' ? '#f59e0b' : '#06b6d4'}
        labelResolution={2}

        hexBinPointsData={showHeatmap ? historicalAnomalies : []}
        hexBinPointWeight="intensity"
        hexAltitude={(d: any) => d.sumWeight * 0.1 + 0.05}
        hexBinResolution={4}
        hexTopColor={(d: any) => `rgba(239, 68, 68, ${d.sumWeight * 0.8 + 0.2})`}
        hexSideColor={(d: any) => `rgba(239, 68, 68, ${d.sumWeight * 0.4})`}
        hexLabel={(d: any) => `
            <div style="background: rgba(15, 23, 42, 0.9); padding: 12px; border: 1px solid #ef4444; border-radius: 8px; color: white; backdrop-filter: blur(8px);">
                <div style="font-weight: bold; color: #ef4444; font-size: 14px; margin-bottom: 4px;">ORBITAL_DANGER_ZONE</div>
                <div style="font-size: 11px; opacity: 0.8;">HISTORICAL_HEATMAP (30D)</div>
                <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid rgba(239, 68, 68, 0.2);">
                    <div style="display: flex; justify-content: space-between;">
                        <span>Density:</span>
                        <span style="font-mono; color: #ef4444;">${Math.round(d.sumWeight * 100)}%</span>
                    </div>
                </div>
            </div>
        `}
      />

      {/* Overlay UI */}
      <div className="absolute top-4 left-4 flex flex-col gap-2">
        <button
          onClick={() => setShowHeatmap(!showHeatmap)}
          className={`px-4 py-2 rounded border text-[10px] font-bold uppercase tracking-widest transition-all ${showHeatmap
            ? 'bg-red-600 border-red-500 text-white shadow-[0_0_15px_rgba(239,68,68,0.4)]'
            : 'bg-slate-900/80 border-slate-700 text-slate-400 hover:border-slate-500'
            }`}
        >
          {showHeatmap ? '⚠️ Heatmap Active' : '🗺️ View Heatmap'}
        </button>
      </div>

      <div className="absolute bottom-4 left-4 bg-slate-900/80 backdrop-blur border border-slate-700 p-3 rounded text-[10px] text-slate-400 font-mono space-y-2 uppercase tracking-tight">
        {!showHeatmap ? (
          <>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-green-500" />
              <span>Signal Clear</span>
            </div>
            <div className="flex items-center gap-2 text-amber-500">
              <div className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
              <span>Weather Interference</span>
            </div>
            <div className="pt-2 border-t border-slate-800">
              Stations: {groundStations.length} // Online
            </div>
          </>
        ) : (
          <>
            <div className="flex items-center gap-2 text-red-500">
              <div className="w-2 h-2 rounded-full bg-red-500" />
              <span>Radiation Anomaly Cluster</span>
            </div>
            <div className="flex items-center gap-2 text-red-300">
              <div className="w-2 h-2 rounded-full bg-red-300 opacity-50" />
              <span>Signal Interference Hotspot</span>
            </div>
            <div className="pt-2 border-t border-slate-800">
              Temporal Window: 30D Historical
            </div>
          </>
        )}
      </div>
    </div>
  );
};
