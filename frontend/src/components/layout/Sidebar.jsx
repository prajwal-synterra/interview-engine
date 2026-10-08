import React from 'react';
import {
  Mic,
  Sliders,
  Terminal,
  BarChart3,
  FileText,
  Settings,
  Cpu
} from 'lucide-react';

export default function Sidebar({ activeNav, setActiveNav, isWsConnected, latency }) {
  const navItems = [
    { id: 'live', label: 'Live Interview', icon: Mic },
    { id: 'features', label: 'Feature Controls', icon: Sliders },
    { id: 'logs', label: 'System Logs', icon: Terminal },
    { id: 'analytics', label: 'Engine Analytics', icon: BarChart3 },
    { id: 'reports', label: 'Reports', icon: FileText },
    { id: 'settings', label: 'Settings', icon: Settings },
  ];

  return (
    <aside className="sidebar">
      <div>
        <div className="brand-section">
          <div className="brand-icon">
            <Cpu size={22} />
          </div>
          <div>
            <h1 className="brand-title">Socratic Interview Engine</h1>
            <p className="brand-subtitle">AI-Powered Interview Platform</p>
          </div>
        </div>

        <nav className="nav-menu">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeNav === item.id;
            return (
              <div
                key={item.id}
                className={`nav-item ${isActive ? 'active' : ''}`}
                onClick={() => setActiveNav(item.id)}
              >
                <Icon size={18} />
                <span>{item.label}</span>
              </div>
            );
          })}
        </nav>
      </div>

      <div className="sidebar-bottom">
        <div className="ws-status-card">
          <div className={`status-dot-pulse ${isWsConnected ? '' : 'red'}`} />
          <div>
            <div className="ws-status-label">FastAPI WebSocket</div>
            <div className="ws-status-meta">
              {isWsConnected ? `Connected • ${latency || '0.8ms'}` : 'Disconnected • Offline'}
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
