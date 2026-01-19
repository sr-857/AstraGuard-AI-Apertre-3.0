'use client';

import { useState } from 'react';

export const VerticalNav: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const navItems = [
    { icon: '🛰️', label: 'Orbit View', href: '#orbit' },
    { icon: '📡', label: 'Telemetry', href: '#telemetry' },
    { icon: '📋', label: 'Logs', href: '#logs' },
    { icon: '⚙️', label: 'Settings', href: '#settings' },
  ];

  return (
    <>
      <button
        className="md:hidden fixed top-20 left-4 z-40 p-2 rounded-lg bg-black/50 glow-cyan border border-cyan-500/30"
        onClick={() => setIsOpen(true)}
        aria-label="Open navigation"
      >
        <svg className="w-6 h-6 text-cyan-400" fill="currentColor" viewBox="0 0 20 20">
          <path d="M3 5h12M3 10h12M3 15h12" stroke="currentColor" strokeWidth="2" />
        </svg>
      </button>

      <aside
        className={`fixed md:static md:translate-x-0 inset-0 w-80 bg-black/95 backdrop-blur-xl border-r border-cyan-500/30 z-30 transform transition-transform ${
          isOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
        }`}
      >
        <div className="p-6 border-b border-cyan-500/20">
          <h2 className="text-xl font-bold text-cyan-400">Navigation</h2>
        </div>
        <nav className="p-4 space-y-2">
          {navItems.map((item) => (
            <a
              key={item.href}
              href={item.href}
              className="flex items-center space-x-3 p-3 rounded-xl text-gray-300 hover:bg-cyan-500/10 hover:text-cyan-400 hover:glow-cyan transition-all duration-300 group"
              onClick={() => setIsOpen(false)}
            >
              <span className="text-2xl">{item.icon}</span>
              <span className="font-mono">{item.label}</span>
            </a>
          ))}
        </nav>
      </aside>

      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-20 md:hidden"
          onClick={() => setIsOpen(false)}
        />
      )}
    </>
  );
};
