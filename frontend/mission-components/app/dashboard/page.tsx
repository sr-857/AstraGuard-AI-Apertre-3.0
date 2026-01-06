'use client';

import { useState } from 'react';
import { MissionState } from '../types/dashboard';
import { DashboardHeader } from '../components/dashboard/DashboardHeader';
import { MissionPanel } from '../components/mission/MissionPanel';
import dashboardData from '../mocks/dashboard.json';

import { SystemsPanel } from '../components/systems/SystemsPanel';

import { DashboardProvider, useDashboard } from '../context/DashboardContext';
import { LoadingSkeleton } from '../components/ui/LoadingSkeleton';
import { TransitionWrapper } from '../components/ui/TransitionWrapper';
import { MobileNavHamburger } from '../components/ui/MobileNavHamburger';
import { DesktopTabNav } from '../components/dashboard/DesktopTabNav';

const DashboardContent: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'mission' | 'systems'>('mission');
  const { isConnected } = useDashboard();
  const mission = dashboardData.mission as MissionState;

  return (
    <div className="dashboard-container min-h-screen text-white font-mono antialiased">
      <DashboardHeader data={mission} />

      <div className="flex min-h-screen pt-[100px] lg:pt-[80px] flex-col">
        <nav className="sticky top-[100px] lg:top-[80px] z-20 bg-black/80 backdrop-blur-xl border-b border-teal-500/30 px-6 flex flex-col md:flex-row md:items-center justify-between flex-shrink-0 mb-4" role="tablist">

          {/* Mobile: Vertical Stack (only visible on mobile) */}
          <MobileNavHamburger activeTab={activeTab} onTabChange={setActiveTab} />

          {/* Desktop: Horizontal (hidden on mobile) */}
          <DesktopTabNav activeTab={activeTab} onTabChange={setActiveTab} />
        </nav>

        <main className="flex-1 px-6 pb-8 relative">
          {!isConnected ? (
            <LoadingSkeleton type="chart" count={6} />
          ) : (
            <>
              {activeTab === 'mission' && (
                <TransitionWrapper isActive={activeTab === 'mission'}>
                  <MissionPanel />
                </TransitionWrapper>
              )}
              {activeTab === 'systems' && (
                <TransitionWrapper isActive={activeTab === 'systems'}>
                  <SystemsPanel />
                </TransitionWrapper>
              )}
            </>
          )}
        </main>

        <footer className="px-6 py-4 border-t border-teal-500/20 text-xs font-mono text-teal-500/40 uppercase tracking-widest flex justify-between items-center backdrop-blur-sm bg-black/20">
          <span>AstraGuard Defense Systems v1.0</span>
          <span>Authorized Personnel Only • Class 1 Clearance</span>
        </footer>
      </div>
    </div>
  );
};

const Dashboard: React.FC = () => {
  return (
    <DashboardProvider>
      <DashboardContent />
    </DashboardProvider>
  );
};

export default Dashboard;
