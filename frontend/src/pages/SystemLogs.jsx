import React, { useState, useEffect } from 'react';
import { Search, RefreshCw, Filter, Download } from 'lucide-react';
import { fetchServerLogs } from '../services/apiService';

export default function SystemLogs({ defaultLogs }) {
  const [logs, setLogs] = useState(defaultLogs || []);
  const [search, setSearch] = useState('');
  const [selectedFilter, setSelectedFilter] = useState('ALL');
  const [isRefreshing, setIsRefreshing] = useState(false);

  const loadLogs = async () => {
    setIsRefreshing(true);
    const serverLogs = await fetchServerLogs(250);
    if (serverLogs && serverLogs.length > 0) {
      // Parse timestamped server lines: [YYYY-MM-DD HH:MM:SS] [CATEGORY] Message
      const parsed = serverLogs.map((line) => {
        const match = line.match(/^\[(.*?)\]\s*\[(.*?)\]\s*(.*)$/);
        if (match) {
          return {
            time: match[1].substring(11),
            severity: 'INFO',
            component: match[2].toLowerCase(),
            message: match[3]
          };
        }
        return {
          time: new Date().toLocaleTimeString(),
          severity: 'LOG',
          component: 'engine',
          message: line
        };
      });
      setLogs(parsed);
    }
    setIsRefreshing(false);
  };

  useEffect(() => {
    loadLogs();
    const interval = setInterval(loadLogs, 3000);
    return () => clearInterval(interval);
  }, []);

  const filteredLogs = logs.filter((log) => {
    const matchesFilter =
      selectedFilter === 'ALL' ||
      log.component.toUpperCase().includes(selectedFilter) ||
      log.severity.toUpperCase().includes(selectedFilter);
    const matchesSearch =
      log.message.toLowerCase().includes(search.toLowerCase()) ||
      log.component.toLowerCase().includes(search.toLowerCase());
    return matchesFilter && matchesSearch;
  });

  return (
    <div className="dashboard-card" style={{ height: 'calc(100vh - 110px)', display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--text)' }}>System Event Logs</h2>
          <p style={{ fontSize: 12, color: 'var(--muted)' }}>
            Real-time event stream from FastAPI live server & logs/interview_engine.log
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <button className="btn btn-secondary" onClick={loadLogs} disabled={isRefreshing}>
            <RefreshCw size={14} className={isRefreshing ? 'spin' : ''} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 14, alignItems: 'center' }}>
        <div className="engine-search-box" style={{ flex: 1, margin: 0 }}>
          <Search size={15} color="var(--muted)" />
          <input
            type="text"
            placeholder="Search log messages or components..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <div style={{ display: 'flex', gap: 6 }}>
          {['ALL', 'WEBSOCKET', 'SHADOW', 'BKT', 'MIRT', 'POLICY', 'DB'].map((f) => (
            <button
              key={f}
              className={`btn-pill-action ${selectedFilter === f ? 'blue' : ''}`}
              onClick={() => setSelectedFilter(f)}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {/* Full-width Terminal Table */}
      <div style={{ flex: 1, overflowY: 'auto', border: '1px solid var(--border)', borderRadius: 8 }}>
        <table className="log-table" style={{ width: '100%' }}>
          <thead>
            <tr>
              <th style={{ width: 100 }}>Timestamp</th>
              <th style={{ width: 80 }}>Severity</th>
              <th style={{ width: 120 }}>Component</th>
              <th>Event Message</th>
            </tr>
          </thead>
          <tbody>
            {filteredLogs.map((log, idx) => (
              <tr key={idx}>
                <td style={{ color: 'var(--muted)', fontFamily: 'var(--font-mono)' }}>{log.time}</td>
                <td>
                  <span className={`log-tag-${log.severity.toLowerCase()}`}>{log.severity}</span>
                </td>
                <td style={{ color: 'var(--blue)', fontWeight: 600 }}>{log.component}</td>
                <td style={{ color: 'var(--text)' }}>{log.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
