import React, { useState, useEffect } from 'react';
import { FileText, RefreshCw, Award, CheckCircle } from 'lucide-react';
import { fetchAllReports, fetchCompactedCards } from '../services/apiService';

export default function ReportsView() {
  const [reports, setReports] = useState([]);
  const [selectedSessionId, setSelectedSessionId] = useState(null);
  const [activeTab, setActiveTab] = useState('evaluator');
  const [compactedCards, setCompactedCards] = useState([]);
  const [isLoading, setIsLoading] = useState(false);

  const loadReports = async () => {
    setIsLoading(true);
    const data = await fetchAllReports();
    setReports(data || []);
    if (data && data.length > 0) {
      setSelectedSessionId(data[0].session_id);
    }
    setIsLoading(false);
  };

  useEffect(() => {
    loadReports();
  }, []);

  useEffect(() => {
    if (selectedSessionId && activeTab === 'cards') {
      fetchCompactedCards(selectedSessionId).then((cards) => setCompactedCards(cards || []));
    }
  }, [selectedSessionId, activeTab]);

  const activeReport = reports.find((r) => r.session_id === selectedSessionId) || reports[0];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div>
          <h2 className="page-title">Candidate Assessment Reports</h2>
          <p className="page-subtitle">
            Persisted candidate evaluations and compacted topic cards from PostgreSQL.
          </p>
        </div>
        <button className="btn btn-secondary" onClick={loadReports} disabled={isLoading}>
          <RefreshCw size={14} className={isLoading ? 'spin' : ''} />
          <span>Refresh Reports</span>
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: 16 }}>
        {/* Sessions list */}
        <div className="dashboard-card" style={{ height: 'calc(100vh - 170px)', overflowY: 'auto' }}>
          <div className="card-heading-sm">
            <span>Past Candidate Sessions</span>
            <span style={{ fontSize: 11, color: 'var(--muted)' }}>{reports.length} Records</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 10 }}>
            {reports.length === 0 ? (
              <div style={{ padding: 20, textAlign: 'center', color: 'var(--muted)', fontSize: 12.5 }}>
                No completed sessions found yet in PostgreSQL. Start an interview to generate reports.
              </div>
            ) : (
              reports.map((r) => {
                const isSelected = r.session_id === selectedSessionId;
                const isHire = r.hiring_verdict?.includes('HIRE');
                return (
                  <div
                    key={r.session_id}
                    onClick={() => setSelectedSessionId(r.session_id)}
                    style={{
                      padding: '10px 12px',
                      borderRadius: 8,
                      border: `1px solid ${isSelected ? 'var(--blue)' : 'var(--border)'}`,
                      backgroundColor: isSelected ? 'var(--blue-light)' : 'var(--surface-2)',
                      cursor: 'pointer'
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <strong style={{ fontSize: 13, color: 'var(--text)' }}>{r.candidate_name || 'Candidate'}</strong>
                      <span className={`pill-status ${isHire ? 'green' : 'orange'}`} style={{ fontSize: 10, padding: '2px 6px' }}>
                        {r.hiring_verdict || 'PENDING'}
                      </span>
                    </div>
                    <div style={{ fontSize: 11.5, color: 'var(--muted)', marginTop: 4 }}>
                      {r.seniority_tier || 'Senior'} • {r.detected_ecosystem || 'Polyglot'}
                    </div>
                    <div style={{ fontSize: 10.5, color: 'var(--text-dim)', marginTop: 2, fontFamily: 'var(--font-mono)' }}>
                      {r.session_id}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Selected Report Content */}
        <div className="dashboard-card" style={{ height: 'calc(100vh - 170px)', display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border)', paddingBottom: 10, marginBottom: 12 }}>
            <div>
              <h3 style={{ fontSize: 15, fontWeight: 700, color: 'var(--text)' }}>
                {activeReport?.candidate_name ? `${activeReport.candidate_name} (${activeReport.seniority_tier})` : 'Select a Session'}
              </h3>
              <p style={{ fontSize: 12, color: 'var(--muted)' }}>
                {activeReport?.session_id} • Verdict: {activeReport?.hiring_verdict || 'N/A'}
              </p>
            </div>

            <div className="debug-tabs-bar" style={{ margin: 0, border: 'none' }}>
              <button
                className={`debug-tab ${activeTab === 'evaluator' ? 'active' : ''}`}
                onClick={() => setActiveTab('evaluator')}
              >
                Evaluator Forensic Audit
              </button>
              <button
                className={`debug-tab ${activeTab === 'student' ? 'active' : ''}`}
                onClick={() => setActiveTab('student')}
              >
                Student Career Compass
              </button>
              <button
                className={`debug-tab ${activeTab === 'cards' ? 'active' : ''}`}
                onClick={() => setActiveTab('cards')}
              >
                Compacted Memory Cards
              </button>
            </div>
          </div>

          <div style={{ flex: 1, overflowY: 'auto', padding: '10px 4px' }}>
            {activeTab === 'cards' ? (
              <div>
                <h4 style={{ fontSize: 13, fontWeight: 700, marginBottom: 10 }}>Compacted Topic Memory</h4>
                {compactedCards.length === 0 ? (
                  <p style={{ color: 'var(--muted)', fontSize: 13 }}>No compacted topic cards recorded for this session.</p>
                ) : (
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                    {compactedCards.map((c, i) => (
                      <div key={i} className="state-chip-box" style={{ padding: 12 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                          <strong style={{ color: 'var(--text)' }}>{c.topic_code}</strong>
                          <span className="pill-status green" style={{ fontSize: 10 }}>{c.status}</span>
                        </div>
                        <div style={{ fontSize: 12, color: 'var(--muted)', margin: '6px 0' }}>
                          {c.verdict_summary}
                        </div>
                        <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)' }}>
                          Final Mastery: {Number(c.final_mastery_p_l).toFixed(2)} | Turns: {c.turns_spent}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <pre
                style={{
                  fontFamily: 'var(--font-sans)',
                  fontSize: 13,
                  lineHeight: 1.6,
                  whiteSpace: 'pre-wrap',
                  color: 'var(--text)'
                }}
              >
                {activeTab === 'evaluator'
                  ? activeReport?.evaluator_audit_markdown || 'No Evaluator Audit Markdown report available for this session.'
                  : activeReport?.student_compass_markdown || 'No Student Career Compass report available for this session.'}
              </pre>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
