import React, { useState, useEffect } from 'react';
import {
  RefreshCw,
  Award,
  CheckCircle,
  MessageSquare,
  Shield,
  Compass,
  Search,
  Sparkles,
  Clock,
  Brain,
  Zap,
  TrendingUp,
  UserCheck,
  AlertTriangle,
  Layers,
  ChevronRight
} from 'lucide-react';
import { marked } from 'marked';
import {
  fetchAllReports,
  fetchSessionReport,
  generateSessionReport,
  fetchCompactedCards
} from '../services/apiService';

// Configure marked options
marked.setOptions({
  gfm: true,
  breaks: true
});

export default function ReportsView() {
  const [sessions, setSessions] = useState([]);
  const [selectedSessionId, setSelectedSessionId] = useState(null);
  const [sessionDetail, setSessionDetail] = useState(null);
  const [activeTab, setActiveTab] = useState('turns');
  const [searchTerm, setSearchTerm] = useState('');
  const [isLoadingList, setIsLoadingList] = useState(false);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generateMessage, setGenerateMessage] = useState(null);

  // 1. Load Sessions List
  const loadSessionsList = async () => {
    setIsLoadingList(true);
    const data = await fetchAllReports();
    setSessions(data || []);
    if (data && data.length > 0 && !selectedSessionId) {
      // Pick first session with turns, or just the first session
      const withTurns = data.find((s) => (s.turns_count || 0) > 0) || data[0];
      setSelectedSessionId(withTurns.session_id);
    }
    setIsLoadingList(false);
  };

  useEffect(() => {
    loadSessionsList();
  }, []);

  // 2. Load Selected Session Details
  const loadSessionDetail = async (sessId) => {
    if (!sessId) return;
    setIsLoadingDetail(true);
    setGenerateMessage(null);
    const data = await fetchSessionReport(sessId);
    setSessionDetail(data);
    setIsLoadingDetail(false);
  };

  useEffect(() => {
    if (selectedSessionId) {
      loadSessionDetail(selectedSessionId);
    }
  }, [selectedSessionId]);

  // 3. Trigger On-Demand Report Generation
  const handleGenerateReport = async () => {
    if (!selectedSessionId) return;
    setIsGenerating(true);
    setGenerateMessage(null);
    try {
      const res = await generateSessionReport(selectedSessionId);
      if (res && res.status === 'success') {
        setGenerateMessage({ type: 'success', text: `Report successfully generated! Hiring Verdict: ${res.hiring_verdict}` });
        await loadSessionDetail(selectedSessionId);
        await loadSessionsList();
      } else {
        setGenerateMessage({ type: 'error', text: res?.detail || 'Could not generate report for this session.' });
      }
    } catch (err) {
      setGenerateMessage({ type: 'error', text: err.message || 'Generation failed' });
    }
    setIsGenerating(false);
  };

  // Filter sessions by search query
  const filteredSessions = sessions.filter((s) => {
    const nameMatch = (s.candidate_name || '').toLowerCase().includes(searchTerm.toLowerCase());
    const idMatch = (s.session_id || '').toLowerCase().includes(searchTerm.toLowerCase());
    const tierMatch = (s.seniority_tier || '').toLowerCase().includes(searchTerm.toLowerCase());
    return nameMatch || idMatch || tierMatch;
  });

  const sessionMeta = sessionDetail?.session || sessions.find((s) => s.session_id === selectedSessionId);
  const turns = sessionDetail?.turns || [];
  const skillsEvaluated = sessionDetail?.skills_evaluated || [];
  const finalReport = sessionDetail?.report || {};
  const cards = sessionDetail?.cards || [];

  const candidateDisplayName = sessionMeta?.candidate_name && sessionMeta?.candidate_name !== ''
    ? sessionMeta.candidate_name
    : 'Candidate';

  const hiringVerdict = finalReport?.hiring_verdict || sessionMeta?.hiring_verdict || 'IN_PROGRESS';
  const isHire = hiringVerdict.includes('HIRE');
  const isPending = hiringVerdict === 'IN_PROGRESS' || hiringVerdict === 'EVALUATED' || hiringVerdict === 'PENDING_FINALIZATION';

  return (
    <div>
      {/* Top Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div>
          <h2 className="page-title">Candidate Assessment & Forensic Audit Reports</h2>
          <p className="page-subtitle">
            Auditable technical evaluations, evaluated competency skills, and turn-by-turn Shadow Evaluator scoring.
          </p>
        </div>
        <button className="btn btn-secondary" onClick={loadSessionsList} disabled={isLoadingList}>
          <RefreshCw size={14} className={isLoadingList ? 'spin' : ''} />
          <span>Refresh Sessions</span>
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: 16 }}>
        {/* Left Column: Sessions List */}
        <div className="dashboard-card" style={{ height: 'calc(100vh - 170px)', display: 'flex', flexDirection: 'column' }}>
          <div className="card-heading-sm">
            <span>Candidate Sessions</span>
            <span style={{ fontSize: 11, color: 'var(--muted)' }}>{sessions.length} Recorded</span>
          </div>

          {/* Search box */}
          <div className="engine-search-box" style={{ margin: '8px 0 12px 0' }}>
            <Search size={14} color="var(--muted)" />
            <input
              type="text"
              placeholder="Filter by name, ID, tier..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>

          {/* List items */}
          <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 8 }}>
            {filteredSessions.length === 0 ? (
              <div style={{ padding: 20, textAlign: 'center', color: 'var(--muted)', fontSize: 12.5 }}>
                No matching sessions found.
              </div>
            ) : (
              filteredSessions.map((s) => {
                const isSelected = s.session_id === selectedSessionId;
                const verdict = s.hiring_verdict || 'IN_PROGRESS';
                const sHire = verdict.includes('HIRE');
                const candName = s.candidate_name && s.candidate_name !== '' ? s.candidate_name : 'Candidate';
                const turnsCount = s.turns_count || 0;

                return (
                  <div
                    key={s.session_id}
                    onClick={() => setSelectedSessionId(s.session_id)}
                    style={{
                      padding: '10px 12px',
                      borderRadius: 8,
                      border: `1px solid ${isSelected ? 'var(--blue)' : 'var(--border)'}`,
                      backgroundColor: isSelected ? 'var(--blue-light)' : 'var(--surface-2)',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <strong style={{ fontSize: 13, color: 'var(--text)' }}>{candName}</strong>
                      <span
                        className={`pill-status ${sHire ? 'green' : verdict === 'IN_PROGRESS' ? 'amber' : 'orange'}`}
                        style={{ fontSize: 10, padding: '2px 6px' }}
                      >
                        {verdict}
                      </span>
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 4, fontSize: 11.5, color: 'var(--muted)' }}>
                      <span>{s.seniority_tier || 'Senior'} • {s.detected_ecosystem || 'Polyglot'}</span>
                      <span style={{ fontWeight: 600, color: turnsCount > 0 ? 'var(--blue)' : 'var(--muted)' }}>
                        {turnsCount} {turnsCount === 1 ? 'Turn' : 'Turns'}
                      </span>
                    </div>

                    <div style={{ fontSize: 10, color: 'var(--text-dim)', marginTop: 4, fontFamily: 'var(--font-mono)' }}>
                      {s.session_id}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right Column: Selected Session Report Detail */}
        <div className="dashboard-card" style={{ height: 'calc(100vh - 170px)', display: 'flex', flexDirection: 'column' }}>
          {isLoadingDetail ? (
            <div style={{ padding: 40, textAlign: 'center', color: 'var(--muted)' }}>
              <RefreshCw size={24} className="spin" style={{ marginBottom: 12 }} />
              <div>Loading forensic report and turn scoring...</div>
            </div>
          ) : !sessionMeta ? (
            <div style={{ padding: 40, textAlign: 'center', color: 'var(--muted)' }}>
              Select a candidate session from the left to view their report and background scoring.
            </div>
          ) : (
            <>
              {/* Executive Header Banner */}
              <div className="report-exec-header">
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <h3 style={{ fontSize: 17, fontWeight: 800, color: 'var(--text)', margin: 0 }}>
                      {candidateDisplayName}
                    </h3>
                    <span className="pill-status blue" style={{ fontSize: 11, padding: '2px 8px' }}>
                      {sessionMeta.seniority_tier || 'Senior'}
                    </span>
                    <span className="pill-status green" style={{ fontSize: 11, padding: '2px 8px' }}>
                      {sessionMeta.detected_ecosystem || 'Polyglot'}
                    </span>
                  </div>
                  <div style={{ fontSize: 11.5, color: 'var(--muted)', marginTop: 4, fontFamily: 'var(--font-mono)' }}>
                    Session: {sessionMeta.session_id}
                  </div>
                </div>

                <div className="report-stat-group">
                  <div className="report-stat-pill">
                    <span className="label">Hiring Verdict</span>
                    <span className="value" style={{ color: isHire ? 'var(--green)' : isPending ? 'var(--orange)' : 'var(--red)' }}>
                      {hiringVerdict}
                    </span>
                  </div>

                  <div className="report-stat-pill">
                    <span className="label">Mastery Score</span>
                    <span className="value" style={{ color: 'var(--blue)' }}>
                      {finalReport.average_mastery !== undefined
                        ? `${(finalReport.average_mastery * 100).toFixed(1)}%`
                        : turns.length > 0
                        ? `${(Number(turns[turns.length - 1].bkt_posterior || 0.65) * 100).toFixed(1)}%`
                        : '—'}
                    </span>
                  </div>

                  <div className="report-stat-pill">
                    <span className="label">Proctor (BII)</span>
                    <span className="value" style={{ color: 'var(--green)' }}>
                      {finalReport.proctor_integrity_score !== undefined
                        ? Number(finalReport.proctor_integrity_score).toFixed(2)
                        : turns.length > 0
                        ? Number(turns[turns.length - 1].proctor_bii || 1.0).toFixed(2)
                        : '1.00'}
                    </span>
                  </div>

                  <div className="report-stat-pill">
                    <span className="label">Turns Evaluated</span>
                    <span className="value" style={{ color: 'var(--purple)' }}>
                      {turns.length}
                    </span>
                  </div>

                  {turns.length > 0 && (!finalReport.student_compass_markdown || !finalReport.evaluator_audit_markdown) && (
                    <button
                      className="btn btn-primary"
                      onClick={handleGenerateReport}
                      disabled={isGenerating}
                      style={{ padding: '8px 14px', fontSize: 12 }}
                    >
                      <Sparkles size={13} className={isGenerating ? 'spin' : ''} />
                      <span>{isGenerating ? 'Compiling Report...' : 'Finalize Report'}</span>
                    </button>
                  )}
                </div>
              </div>

              {generateMessage && (
                <div
                  style={{
                    padding: '8px 14px',
                    borderRadius: 6,
                    marginBottom: 10,
                    fontSize: 12.5,
                    backgroundColor: generateMessage.type === 'success' ? 'var(--green-light)' : 'var(--red-light)',
                    color: generateMessage.type === 'success' ? 'var(--green)' : 'var(--red)',
                    border: `1px solid ${generateMessage.type === 'success' ? 'var(--green-border)' : 'var(--red-border)'}`
                  }}
                >
                  {generateMessage.text}
                </div>
              )}

              {/* Navigation Tabs Bar */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border)', paddingBottom: 10, marginBottom: 14 }}>
                <div className="debug-tabs-bar" style={{ margin: 0, border: 'none' }}>
                  <button
                    className={`debug-tab ${activeTab === 'turns' ? 'active' : ''}`}
                    onClick={() => setActiveTab('turns')}
                  >
                    <MessageSquare size={13} style={{ marginRight: 6 }} />
                    Conversational Audit & Scoring ({turns.length})
                  </button>
                  <button
                    className={`debug-tab ${activeTab === 'skills' ? 'active' : ''}`}
                    onClick={() => setActiveTab('skills')}
                  >
                    <Award size={13} style={{ marginRight: 6 }} />
                    Evaluated Skills & Fields ({skillsEvaluated.length})
                  </button>
                  <button
                    className={`debug-tab ${activeTab === 'evaluator' ? 'active' : ''}`}
                    onClick={() => setActiveTab('evaluator')}
                  >
                    <Shield size={13} style={{ marginRight: 6 }} />
                    Forensic Audit Report
                  </button>
                  <button
                    className={`debug-tab ${activeTab === 'student' ? 'active' : ''}`}
                    onClick={() => setActiveTab('student')}
                  >
                    <Compass size={13} style={{ marginRight: 6 }} />
                    Student Career Compass
                  </button>
                  <button
                    className={`debug-tab ${activeTab === 'cards' ? 'active' : ''}`}
                    onClick={() => setActiveTab('cards')}
                  >
                    <Layers size={13} style={{ marginRight: 6 }} />
                    Compacted Topic Cards ({cards.length})
                  </button>
                </div>
              </div>

              {/* Tab 1: Turn-by-Turn Conversational Audit & Shadow Scoring */}
              {activeTab === 'turns' && (
                <div style={{ flex: 1, overflowY: 'auto', paddingRight: 6 }}>
                  <div style={{ padding: '10px 14px', backgroundColor: '#F8FAFC', borderRadius: 8, border: '1px solid var(--border)', marginBottom: 14, fontSize: 12.5, color: 'var(--muted)' }}>
                    <strong>Shadow Evaluator Turn Trail:</strong> Every conversation turn shows Alex's architectural prompt, candidate spoken transcript, and background scoring (observation, depth score, BKT mastery shift, and rubric reasoning).
                  </div>

                  {turns.length === 0 ? (
                    <div style={{ padding: 40, textAlign: 'center', color: 'var(--muted)' }}>
                      <MessageSquare size={32} style={{ marginBottom: 10, opacity: 0.4 }} />
                      <div style={{ fontSize: 14, fontWeight: 600 }}>No conversational turns recorded for this session yet.</div>
                      <p style={{ fontSize: 12, marginTop: 4 }}>
                        During the interview, as candidate answers Alex's technical questions, every interaction will be scored and listed here in real-time.
                      </p>
                    </div>
                  ) : (
                    <div className="turn-audit-list">
                      {turns.map((t, idx) => {
                        const obs = t.evaluator_observation;
                        const isPass = obs === 1;
                        const isPartial = obs === 2;
                        const depthPct = Math.round((t.depth_score || 0.65) * 100);
                        const bktPrior = t.bkt_prior !== undefined ? Number(t.bkt_prior).toFixed(2) : '0.40';
                        const bktPost = t.bkt_posterior !== undefined ? Number(t.bkt_posterior).toFixed(2) : '0.72';
                        const bktDelta = (Number(bktPost) - Number(bktPrior)).toFixed(2);
                        const latency = t.latency_ms || 1400;
                        const bii = t.proctor_bii !== undefined ? Number(t.proctor_bii).toFixed(2) : '1.00';
                        const scaffoldLvl = t.scaffolding_level || 0;

                        return (
                          <div key={t.turn_id || idx} className="turn-audit-card">
                            {/* Turn Header */}
                            <div className="turn-audit-header">
                              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                                <span className="turn-badge">Turn #{t.turn_index || idx + 1}</span>
                                <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--blue)' }}>
                                  {t.topic ? t.topic.replace(/_/g, ' ') : 'SYSTEM DESIGN'}
                                </span>
                              </div>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 14, fontSize: 11.5, color: 'var(--muted)' }}>
                                <span><Clock size={12} style={{ verticalAlign: 'middle', marginRight: 4 }} />{latency}ms latency</span>
                                <span className={`pill-status ${isPass ? 'green' : isPartial ? 'orange' : 'red'}`} style={{ fontSize: 10.5, padding: '2px 8px' }}>
                                  {isPass ? '● OBSERVATION: PASS' : isPartial ? '● OBSERVATION: PARTIAL' : '● OBSERVATION: FAIL'}
                                </span>
                              </div>
                            </div>

                            {/* Dialogue Thread */}
                            <div className="turn-dialogue-container">
                              {/* Interviewer Question */}
                              <div className="dialogue-bubble-row">
                                <div className="dialogue-avatar alex">Alex</div>
                                <div className="dialogue-bubble alex">
                                  <div className="dialogue-speaker-name" style={{ color: 'var(--blue)' }}>Alex (Principal Architect Interviewer)</div>
                                  <div>{t.interviewer_prompt || 'Technical architectural question.'}</div>
                                </div>
                              </div>

                              {/* Candidate Answer */}
                              <div className="dialogue-bubble-row">
                                <div className="dialogue-avatar candidate">You</div>
                                <div className="dialogue-bubble candidate">
                                  <div className="dialogue-speaker-name" style={{ color: 'var(--green)' }}>
                                    {candidateDisplayName} (Candidate Response)
                                  </div>
                                  <div>{t.candidate_transcript || '(No speech transcript recorded)'}</div>
                                </div>
                              </div>
                            </div>

                            {/* Shadow Evaluator Background Scoring Panel */}
                            <div className="shadow-scoring-box">
                              <div className="shadow-scoring-header">
                                <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#6B21A8', fontWeight: 700, fontSize: 12 }}>
                                  <Brain size={15} />
                                  <span>Shadow Evaluator Background Scoring & Cognitive Updates</span>
                                </div>
                                <span style={{ fontSize: 11, color: '#7E22CE', fontFamily: 'var(--font-mono)' }}>
                                  Turn ID: {t.turn_id || `turn_${idx + 1}`}
                                </span>
                              </div>

                              {/* Metrics Grid */}
                              <div className="shadow-metrics-grid">
                                <div className="shadow-metric-chip">
                                  <div className="label">Evaluation Verdict</div>
                                  <div className="value" style={{ color: isPass ? 'var(--green)' : isPartial ? 'var(--orange)' : 'var(--red)' }}>
                                    {isPass ? 'Positive Match (Obs 1)' : isPartial ? 'Partial Match (Obs 2)' : 'Deficient (Obs 0)'}
                                  </div>
                                </div>

                                <div className="shadow-metric-chip">
                                  <div className="label">Architectural Depth</div>
                                  <div className="value" style={{ color: 'var(--purple)' }}>
                                    {depthPct}% Depth Score
                                  </div>
                                </div>

                                <div className="shadow-metric-chip">
                                  <div className="label">BKT Mastery Shift</div>
                                  <div className="value" style={{ color: 'var(--blue)' }}>
                                    {bktPrior} → {bktPost} ({Number(bktDelta) >= 0 ? `+${bktDelta}` : bktDelta})
                                  </div>
                                </div>

                                <div className="shadow-metric-chip">
                                  <div className="label">Proctor Integrity</div>
                                  <div className="value" style={{ color: 'var(--green)' }}>
                                    {bii} BII (Verified)
                                  </div>
                                </div>

                                <div className="shadow-metric-chip">
                                  <div className="label">Scaffolding Used</div>
                                  <div className="value" style={{ color: scaffoldLvl > 0 ? 'var(--orange)' : 'var(--text)' }}>
                                    {scaffoldLvl === 0 ? 'Autonomous (L0)' : `Hint Level ${scaffoldLvl}`}
                                  </div>
                                </div>
                              </div>

                              {/* Shadow Evaluator Feedback / Reason */}
                              {t.evaluator_feedback && t.evaluator_feedback.trim() && (
                                <div className="shadow-feedback-text">
                                  <strong>Evaluator Rubric Analysis:</strong> {t.evaluator_feedback}
                                </div>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}

              {/* Tab 2: Evaluated Competency Fields & Skills */}
              {activeTab === 'skills' && (
                <div style={{ flex: 1, overflowY: 'auto', paddingRight: 6 }}>
                  <div style={{ padding: '10px 14px', backgroundColor: '#F8FAFC', borderRadius: 8, border: '1px solid var(--border)', marginBottom: 16, fontSize: 12.5, color: 'var(--muted)' }}>
                    <strong>Evaluated Competency Fields:</strong> Technical pillars identified and matched to the candidate's background, showing mastery certification, domain criticality, and turns tested.
                  </div>

                  {skillsEvaluated.length === 0 ? (
                    <div style={{ padding: 40, textAlign: 'center', color: 'var(--muted)' }}>
                      <Award size={32} style={{ marginBottom: 10, opacity: 0.4 }} />
                      <div style={{ fontSize: 14, fontWeight: 600 }}>No competency pillars registered for this session.</div>
                    </div>
                  ) : (
                    <div className="skills-evaluated-grid">
                      {skillsEvaluated.map((s, idx) => {
                        const mastery = s.final_mastery !== undefined ? Number(s.final_mastery) : 0.65;
                        const masteryPct = Math.round(mastery * 100);
                        const statusClass = mastery >= 0.85 ? 'mastered' : mastery >= 0.60 ? 'competent' : 'developing';
                        const statusLabel = mastery >= 0.85 ? 'CERTIFIED MASTERED' : mastery >= 0.60 ? 'COMPETENT' : 'DEVELOPING';
                        const statusColor = mastery >= 0.85 ? 'var(--green)' : mastery >= 0.60 ? 'var(--blue)' : 'var(--orange)';

                        return (
                          <div key={s.pillar_id || idx} className={`skill-eval-card ${statusClass}`}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                              <div>
                                <span style={{ fontSize: 10.5, textTransform: 'uppercase', color: 'var(--muted)', fontWeight: 700, letterSpacing: 0.4 }}>
                                  {s.domain || 'SYSTEM_DESIGN'}
                                </span>
                                <h4 style={{ fontSize: 14, fontWeight: 700, color: 'var(--text)', marginTop: 2 }}>
                                  {s.name || s.pillar_id.replace(/_/g, ' ')}
                                </h4>
                              </div>
                              <span className={`pill-status ${s.criticality === 'HIGH' ? 'red' : 'blue'}`} style={{ fontSize: 10, padding: '2px 6px' }}>
                                {s.criticality || 'HIGH'}
                              </span>
                            </div>

                            {/* Probe question */}
                            {s.probe && (
                              <p style={{ fontSize: 12, color: 'var(--muted)', fontStyle: 'italic', margin: '4px 0' }}>
                                "{s.probe}"
                              </p>
                            )}

                            {/* Mastery Gauge */}
                            <div style={{ marginTop: 'auto' }}>
                              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                                <span style={{ fontSize: 11, fontWeight: 700, color: statusColor }}>{statusLabel}</span>
                                <span style={{ fontSize: 12, fontWeight: 800, color: 'var(--text)' }}>{masteryPct}% Mastery</span>
                              </div>
                              <div className="progress-track" style={{ height: 8 }}>
                                <div
                                  className="progress-fill-purple"
                                  style={{
                                    width: `${masteryPct}%`,
                                    backgroundColor: statusColor
                                  }}
                                />
                              </div>
                              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6, fontSize: 11, color: 'var(--muted)' }}>
                                <span>P(L) = {mastery.toFixed(2)}</span>
                                <span>{s.turns_count || 0} Turns Spent</span>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}

              {/* Tab 3: Evaluator Forensic Audit (Markdown HTML) */}
              {activeTab === 'evaluator' && (
                <div style={{ flex: 1, overflowY: 'auto', padding: '10px 14px' }}>
                  {finalReport.evaluator_audit_markdown ? (
                    <div
                      className="markdown-report-content"
                      dangerouslySetInnerHTML={{ __html: marked.parse(finalReport.evaluator_audit_markdown) }}
                    />
                  ) : (
                    <div style={{ padding: 40, textAlign: 'center', color: 'var(--muted)' }}>
                      <Shield size={32} style={{ marginBottom: 10, opacity: 0.4 }} />
                      <div style={{ fontSize: 14, fontWeight: 600 }}>Forensic Audit Report not generated yet.</div>
                      {turns.length > 0 && (
                        <button className="btn btn-primary" onClick={handleGenerateReport} disabled={isGenerating} style={{ marginTop: 14 }}>
                          <Sparkles size={14} />
                          <span>Generate Forensic Audit Report</span>
                        </button>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* Tab 4: Student Career Compass (Markdown HTML) */}
              {activeTab === 'student' && (
                <div style={{ flex: 1, overflowY: 'auto', padding: '10px 14px' }}>
                  {finalReport.student_compass_markdown ? (
                    <div
                      className="markdown-report-content"
                      dangerouslySetInnerHTML={{ __html: marked.parse(finalReport.student_compass_markdown) }}
                    />
                  ) : (
                    <div style={{ padding: 40, textAlign: 'center', color: 'var(--muted)' }}>
                      <Compass size={32} style={{ marginBottom: 10, opacity: 0.4 }} />
                      <div style={{ fontSize: 14, fontWeight: 600 }}>Student Career Compass Report not generated yet.</div>
                      {turns.length > 0 && (
                        <button className="btn btn-primary" onClick={handleGenerateReport} disabled={isGenerating} style={{ marginTop: 14 }}>
                          <Sparkles size={14} />
                          <span>Generate Career Compass Report</span>
                        </button>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* Tab 5: Compacted Topic Cards */}
              {activeTab === 'cards' && (
                <div style={{ flex: 1, overflowY: 'auto', paddingRight: 6 }}>
                  <div style={{ padding: '10px 14px', backgroundColor: '#F8FAFC', borderRadius: 8, border: '1px solid var(--border)', marginBottom: 16, fontSize: 12.5, color: 'var(--muted)' }}>
                    <strong>Compacted Topic Memory Cards:</strong> Long-term memory summaries created by the policy router as candidate transitions across technical pillars.
                  </div>

                  {cards.length === 0 ? (
                    <div style={{ padding: 40, textAlign: 'center', color: 'var(--muted)' }}>
                      <Layers size={32} style={{ marginBottom: 10, opacity: 0.4 }} />
                      <div style={{ fontSize: 14, fontWeight: 600 }}>No compacted topic cards recorded for this session.</div>
                    </div>
                  ) : (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 14 }}>
                      {cards.map((c, i) => (
                        <div key={c.card_id || i} className="state-chip-box" style={{ padding: 14, borderRadius: 8 }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <strong style={{ color: 'var(--text)', fontSize: 13.5 }}>{c.topic_code}</strong>
                            <span className="pill-status green" style={{ fontSize: 10 }}>{c.status}</span>
                          </div>
                          <div style={{ fontSize: 12, color: 'var(--muted)', margin: '8px 0', lineHeight: 1.5 }}>
                            {c.verdict_summary}
                          </div>
                          <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--blue)' }}>
                            Final Mastery: {Number(c.final_mastery_p_l || 0).toFixed(2)} | Turns: {c.turns_spent || 0}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
