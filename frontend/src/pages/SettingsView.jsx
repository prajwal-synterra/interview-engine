import React from 'react';
import { Settings, Server, Database, Key, ShieldCheck } from 'lucide-react';

export default function SettingsView({ isWsConnected }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div>
        <h2 className="page-title">Developer Console Settings</h2>
        <p className="page-subtitle">
          Configure backend ports, Gemini Live model targets, and database connections.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <div className="dashboard-card">
          <div className="card-heading-sm">
            <span>FastAPI Server Configuration</span>
            <span className={`pill-status ${isWsConnected ? 'green' : 'red'}`}>
              ● {isWsConnected ? 'Active' : 'Offline'}
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 12 }}>
            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--muted)' }}>Backend URL</label>
              <input
                type="text"
                className="candidate-text-input"
                style={{ width: '100%', marginTop: 4 }}
                defaultValue="http://127.0.0.1:8000"
                readOnly
              />
            </div>

            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--muted)' }}>WebSocket Endpoint</label>
              <input
                type="text"
                className="candidate-text-input"
                style={{ width: '100%', marginTop: 4 }}
                defaultValue="ws://127.0.0.1:8000/ws/interview"
                readOnly
              />
            </div>

            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--muted)' }}>Gemini Live Voice Model</label>
              <input
                type="text"
                className="candidate-text-input"
                style={{ width: '100%', marginTop: 4 }}
                defaultValue="gemini-3.8-live"
                readOnly
              />
            </div>
          </div>
        </div>

        <div className="dashboard-card">
          <div className="card-heading-sm">
            <span>PostgreSQL Database Connection</span>
            <span className="pill-status green">● Connected</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 12 }}>
            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--muted)' }}>Database Host & Port</label>
              <input
                type="text"
                className="candidate-text-input"
                style={{ width: '100%', marginTop: 4 }}
                defaultValue="localhost:5432"
                readOnly
              />
            </div>

            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--muted)' }}>Database Name</label>
              <input
                type="text"
                className="candidate-text-input"
                style={{ width: '100%', marginTop: 4 }}
                defaultValue="interview-engine"
                readOnly
              />
            </div>

            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--muted)' }}>Driver Architecture</label>
              <input
                type="text"
                className="candidate-text-input"
                style={{ width: '100%', marginTop: 4 }}
                defaultValue="pg8000.dbapi (Pure Python / Zero binary DLLs)"
                readOnly
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
