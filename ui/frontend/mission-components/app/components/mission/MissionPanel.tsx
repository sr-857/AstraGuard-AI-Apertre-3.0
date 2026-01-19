import { useState } from 'react';
import { SatelliteFleetTable } from './SatelliteFleetTable';
import { MissionTimeline } from './MissionTimeline';
import { OrbitMap } from './OrbitMap';
import { AnomalyFeed } from './AnomalyFeed';
import { useDashboard } from '../../context/DashboardContext';



interface Props {
  onInvestigate: (anomaly: any) => void;
}

export const MissionPanel: React.FC<Props> = ({ onInvestigate }) => {
  const { state, send } = useDashboard();
  const { satellites, phases, anomalies } = state.mission;

  const [selectedSatId, setSelectedSatId] = useState<string | null>(null);

  // ...

  // Scroll down to where AnomalyFeed is rendered



  const selectedSat = satellites.find((s) => s.id === selectedSatId) || null;

  const handleAcknowledgeAnomaly = (id: string) => {
    send({
      type: 'anomaly_ack',
      payload: { id },
      timestamp: new Date().toISOString()
    });
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 max-w-[1600px] mx-auto">
      {/* Left Column: Orbit & Timeline (8 cols) */}
      <div className="lg:col-span-8 space-y-6">
        {/* Orbit Visualization */}
        <div className="panel-base h-[400px]">
          <div className="panel-header">
            <h3 className="panel-title">Orbit Visualization</h3>
            <span className="text-xs text-slate-500">Live Tracking</span>
          </div>
          <div className="h-[calc(100%-48px)]">
            <OrbitMap
              satellites={satellites}
              selectedSat={selectedSat}
              onSatClick={(sat) => setSelectedSatId(sat.id)}
              anomalies={anomalies.filter((a) => !a.acknowledged)}
            />
          </div>
        </div>

        {/* Mission Phase Timeline */}
        <MissionTimeline phases={phases} />
      </div>

      {/* Right Column: Fleet & Anomalies (4 cols) */}
      <div className="lg:col-span-4 space-y-6">
        {/* Satellite Fleet Table */}
        <SatelliteFleetTable satellites={satellites} />

        {/* Anomaly Feed */}
        <div className="panel-base p-0 overflow-hidden">
          <div className="panel-header bg-slate-900">
            <h3 className="panel-title text-red-400">Anomaly Feed</h3>
            <span className="text-xs text-slate-500">Real-time alerts</span>
          </div>
          <AnomalyFeed
            anomalies={anomalies}
            onAcknowledge={handleAcknowledgeAnomaly}
            onSelect={() => { }}
            onInvestigate={onInvestigate}
            selectedSat={selectedSat?.orbitSlot || null}
          />
        </div>
      </div>
    </div>
  );
};
