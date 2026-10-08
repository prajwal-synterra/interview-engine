import React from 'react';
import { Play, Pause, Square, Bell, ChevronDown } from 'lucide-react';

export default function Topbar({
  sessionId,
  isWsConnected,
  duration,
  isInterviewRunning,
  isPaused,
  onStart,
  onPause,
  onEnd
}) {
  return (
    <header className="topbar">
      <div className="topbar-left">
        <div className="session-badge-wrap">
          <span>Session ID:</span>
          <span className="session-id-pill">{sessionId || 'sess_2025_09_30_1745_001'}</span>
        </div>

        <div className={`pill-status ${isWsConnected ? 'green' : 'red'}`}>
          <div className={`status-dot-pulse ${isWsConnected ? '' : 'red'}`} style={{ width: 6, height: 6 }} />
          <span>WebSocket: {isWsConnected ? 'Connected' : 'Offline'}</span>
        </div>

        <div className="duration-clock">
          <span style={{ color: 'var(--muted)', fontWeight: 500 }}>Duration:</span>
          <span>{duration}</span>
        </div>
      </div>

      <div className="topbar-right">
        {!isInterviewRunning ? (
          <button className="btn btn-primary" onClick={onStart}>
            <Play size={14} fill="white" />
            <span>Start</span>
          </button>
        ) : (
          <>
            <button className="btn btn-secondary" onClick={onPause}>
              <Pause size={14} />
              <span>{isPaused ? 'Resume' : 'Pause'}</span>
            </button>
            <button className="btn btn-danger-outline" onClick={onEnd}>
              <Square size={14} />
              <span>End Session</span>
            </button>
          </>
        )}

        <button className="btn btn-secondary" style={{ padding: '8px 10px' }} title="Notifications">
          <Bell size={16} />
        </button>

        <div className="user-profile-badge">
          <div className="user-avatar">PG</div>
          <div>
            <div className="user-meta-name">Prajwal</div>
            <div className="user-meta-role">Developer</div>
          </div>
          <ChevronDown size={14} color="var(--muted)" />
        </div>
      </div>
    </header>
  );
}
