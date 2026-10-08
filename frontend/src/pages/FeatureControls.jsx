import React, { useState } from 'react';
import {
  Search,
  AlertTriangle,
  Play,
  CheckCircle2,
  XCircle,
  Clock,
  Layers,
  Radio,
  Sparkles,
  Shield,
  Database,
  Cpu,
  BarChart2,
  FileText
} from 'lucide-react';

export default function FeatureControls({ features, setFeatures }) {
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedEngineId, setSelectedEngineId] = useState('shadow_eval');
  const [activeTab, setActiveTab] = useState('config');
  const [isExecutingTest, setIsExecutingTest] = useState(false);
  const [testResult, setTestResult] = useState(null);

  const categories = [
    { name: 'All', count: features.length },
    { name: 'Real-Time Communication', count: features.filter(f => f.category === 'Real-Time Communication').length },
    { name: 'LLM Processing', count: features.filter(f => f.category === 'LLM Processing').length },
    { name: 'Evaluation', count: features.filter(f => f.category === 'Evaluation').length },
    { name: 'Scoring', count: features.filter(f => f.category === 'Scoring').length },
    { name: 'Adaptive Learning', count: features.filter(f => f.category === 'Adaptive Learning').length },
    { name: 'Security', count: features.filter(f => f.category === 'Security').length },
    { name: 'Persistence', count: features.filter(f => f.category === 'Persistence').length || 2 },
    { name: 'Reporting', count: features.filter(f => f.category === 'Reporting').length }
  ];

  const filteredEngines = features.filter((feat) => {
    const matchesCat = selectedCategory === 'All' || feat.category === selectedCategory;
    const matchesSearch =
      feat.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      feat.category.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCat && matchesSearch;
  });

  const selectedEngine = features.find((f) => f.id === selectedEngineId) || features[1] || features[0];

  const toggleEngine = (id) => {
    setFeatures((prev) =>
      prev.map((f) => {
        if (f.id === id) {
          const nextEnabled = !f.enabled;
          return {
            ...f,
            enabled: nextEnabled,
            status: nextEnabled ? 'Active' : 'Disabled'
          };
        }
        return f;
      })
    );
  };

  const runTestExecution = () => {
    setIsExecutingTest(true);
    setTestResult(null);
    setTimeout(() => {
      setIsExecutingTest(false);
      setTestResult({
        status: 'Success',
        duration: '1.8s',
        timestamp: new Date().toLocaleTimeString(),
        tokens: '1,192 / 340'
      });
    }, 1200);
  };

  return (
    <div>
      <div className="features-page-header">
        <h2 className="page-title">Feature Testing and Configuration</h2>
        <p className="page-subtitle">
          Test and configure individual engines. Changes affect real backend functionality.
        </p>
      </div>

      <div className="features-grid-4col">
        {/* Column 1: Engine Categories */}
        <div className="dashboard-card" style={{ padding: '14px 12px' }}>
          <div className="card-heading-sm" style={{ padding: '0 4px', marginBottom: 8 }}>
            <span>Engine Categories</span>
          </div>
          <div className="category-nav-list">
            {categories.map((cat) => (
              <div
                key={cat.name}
                className={`category-nav-item ${selectedCategory === cat.name ? 'active' : ''}`}
                onClick={() => setSelectedCategory(cat.name)}
              >
                <span>{cat.name}</span>
                <span className="category-count-badge">{cat.count}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Column 2: Available Engines */}
        <div className="dashboard-card" style={{ padding: '14px 12px' }}>
          <div className="card-heading-sm" style={{ padding: '0 4px', marginBottom: 8 }}>
            <span>Available Engines</span>
          </div>

          <div className="engine-search-box">
            <Search size={15} color="var(--muted)" />
            <input
              type="text"
              placeholder="Search engines..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          <div style={{ maxHeight: '640px', overflowY: 'auto', paddingRight: 4 }}>
            {filteredEngines.map((eng) => {
              const isSelected = eng.id === selectedEngine.id;
              const statusColor = eng.enabled ? 'green' : 'red';
              return (
                <div
                  key={eng.id}
                  className={`available-engine-item ${isSelected ? 'active' : ''}`}
                  onClick={() => setSelectedEngineId(eng.id)}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div
                      style={{
                        width: 24,
                        height: 24,
                        borderRadius: 6,
                        backgroundColor: eng.enabled ? 'var(--blue-light)' : 'var(--surface-2)',
                        color: eng.enabled ? 'var(--blue)' : 'var(--muted)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center'
                      }}
                    >
                      <Cpu size={14} />
                    </div>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>
                        {eng.name}
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--muted)' }}>{eng.category}</div>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <label
                      className="switch"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <input
                        type="checkbox"
                        checked={eng.enabled}
                        onChange={() => toggleEngine(eng.id)}
                      />
                      <span className="slider" />
                    </label>
                    <span
                      className={`pill-status ${statusColor}`}
                      style={{ padding: '2px 6px', fontSize: 10 }}
                    >
                      {eng.enabled ? 'Active' : 'Disabled'}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Column 3: Selected Engine Details */}
        <div className="dashboard-card">
          <div className="engine-detail-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div
                style={{
                  width: 38,
                  height: 38,
                  borderRadius: 8,
                  backgroundColor: 'var(--purple-light)',
                  color: 'var(--purple)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}
              >
                <Sparkles size={20} />
              </div>
              <div>
                <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text)' }}>
                  {selectedEngine.name}
                </h3>
                <p style={{ fontSize: 12, color: 'var(--muted)' }}>
                  {selectedEngine.description}
                </p>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <label className="switch">
                <input
                  type="checkbox"
                  checked={selectedEngine.enabled}
                  onChange={() => toggleEngine(selectedEngine.id)}
                />
                <span className="slider" />
              </label>
              <span className={`pill-status ${selectedEngine.enabled ? 'green' : 'red'}`}>
                ● {selectedEngine.enabled ? 'Enabled' : 'Disabled'}
              </span>
            </div>
          </div>

          {/* Sub-tabs */}
          <div className="debug-tabs-bar" style={{ marginBottom: 14 }}>
            {[
              { id: 'config', label: 'Configuration' },
              { id: 'deps', label: 'Dependencies' },
              { id: 'history', label: 'Execution History' }
            ].map((tab) => (
              <button
                key={tab.id}
                className={`debug-tab ${activeTab === tab.id ? 'active' : ''}`}
                onClick={() => setActiveTab(tab.id)}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Module Information */}
          <div style={{ marginBottom: 14 }}>
            <h4 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)', marginBottom: 8 }}>
              Module Information
            </h4>
            <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: '6px 12px', fontSize: 12.5 }}>
              <span style={{ color: 'var(--muted)' }}>Backend Module</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{selectedEngine.backendModule}</span>

              <span style={{ color: 'var(--muted)' }}>Service</span>
              <span style={{ fontFamily: 'var(--font-mono)' }}>{selectedEngine.service}</span>

              <span style={{ color: 'var(--muted)' }}>Dependencies</span>
              <span>{selectedEngine.dependencies}</span>
            </div>
          </div>

          {/* Input / Output Preview */}
          <div>
            <h4 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)', marginBottom: 8 }}>
              Input / Output Preview
            </h4>

            <div style={{ fontSize: 11.5, fontWeight: 600, color: 'var(--muted)', marginBottom: 4 }}>
              Input (sample)
            </div>
            <pre className="json-code-box">
              {JSON.stringify(selectedEngine.sampleInput, null, 2)}
            </pre>

            <div style={{ fontSize: 11.5, fontWeight: 600, color: 'var(--muted)', marginBottom: 4 }}>
              Output (sample)
            </div>
            <pre className="json-code-box">
              {JSON.stringify(selectedEngine.sampleOutput, null, 2)}
            </pre>
          </div>

          <button
            className="btn btn-primary"
            style={{ width: '100%', marginTop: 8 }}
            onClick={runTestExecution}
            disabled={isExecutingTest}
          >
            <Play size={14} />
            <span>{isExecutingTest ? 'Running Test Execution...' : 'Test Execution'}</span>
          </button>
        </div>

        {/* Column 4: Far-Right Inspector & History */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {/* Dependency Warning */}
          <div className="warning-alert-card">
            <AlertTriangle size={18} style={{ flexShrink: 0, marginTop: 2 }} />
            <div>
              <div style={{ fontWeight: 700, marginBottom: 2 }}>Dependency Warning</div>
              <div>
                Disabling this feature will prevent new evaluation observations which may stop BKT and MIRT from receiving normal updates.
              </div>
            </div>
          </div>

          {/* Last Execution Card */}
          <div className="dashboard-card">
            <div className="card-heading-sm">
              <span>Last Execution</span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 12.5 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--muted)' }}>Status</span>
                <span className="pill-status green" style={{ padding: '2px 8px', fontSize: 11 }}>
                  ● {testResult?.status || selectedEngine.lastExecution.status}
                </span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--muted)' }}>Duration</span>
                <span style={{ fontWeight: 600 }}>
                  {testResult?.duration || selectedEngine.lastExecution.duration}
                </span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--muted)' }}>Timestamp</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5 }}>
                  {testResult?.timestamp || selectedEngine.lastExecution.timestamp}
                </span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--muted)' }}>Tokens (in/out)</span>
                <span style={{ fontFamily: 'var(--font-mono)' }}>
                  {testResult?.tokens || selectedEngine.lastExecution.tokens}
                </span>
              </div>
            </div>

            <div style={{ marginTop: 14, paddingTop: 10, borderTop: '1px solid var(--border)' }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text)', marginBottom: 2 }}>
                Recent Errors
              </div>
              <div style={{ fontSize: 12, color: 'var(--muted)' }}>None</div>
            </div>
          </div>

          {/* Execution History */}
          <div className="dashboard-card">
            <div className="card-heading-sm">
              <span>Execution History</span>
              <a href="#viewall" style={{ fontSize: 11.5, color: 'var(--blue)', textDecoration: 'none' }}>
                View All
              </a>
            </div>

            <table className="log-table" style={{ fontSize: 11.5 }}>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Status</th>
                  <th>Duration</th>
                  <th>Tokens</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td style={{ color: 'var(--muted)' }}>17:42:18</td>
                  <td><span className="pill-status green" style={{ padding: '1px 5px', fontSize: 10 }}>Success</span></td>
                  <td>2.4s</td>
                  <td>1,248/356</td>
                </tr>
                <tr>
                  <td style={{ color: 'var(--muted)' }}>17:40:11</td>
                  <td><span className="pill-status green" style={{ padding: '1px 5px', fontSize: 10 }}>Success</span></td>
                  <td>2.1s</td>
                  <td>1,102/312</td>
                </tr>
                <tr>
                  <td style={{ color: 'var(--muted)' }}>17:37:05</td>
                  <td><span className="pill-status red" style={{ padding: '1px 5px', fontSize: 10 }}>Failed</span></td>
                  <td>4.8s</td>
                  <td>0/0</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
