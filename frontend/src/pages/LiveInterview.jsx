import React, { useState, useEffect, useRef } from 'react';
import {
  Mic,
  Send,
  Bot,
  Sparkles,
  Radio,
  CheckCircle2,
  Clock,
  ArrowRight,
  Shield,
  Layers,
  Activity,
  Cpu
} from 'lucide-react';

export default function LiveInterview({
  features,
  setFeatures,
  onSendCandidateMessage,
  onToggleMic,
  isRecordingMic,
  conversationHistory,
  activityTimeline,
  pipelineStatus,
  telemetry,
  debugLogs,
  isAlexSpeaking
}) {
  const [inputText, setInputText] = useState('');
  const [activeDebugTab, setActiveDebugTab] = useState('system');
  const chatScrollRef = useRef(null);

  // Auto-scroll conversation
  useEffect(() => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight;
    }
  }, [conversationHistory]);

  const handleSend = (e) => {
    e?.preventDefault();
    if (!inputText.trim()) return;
    onSendCandidateMessage(inputText.trim());
    setInputText('');
  };

  const toggleFeature = (id) => {
    setFeatures((prev) =>
      prev.map((f) => (f.id === id ? { ...f, enabled: !f.enabled } : f))
    );
  };

  const enableAll = () => {
    setFeatures((prev) => prev.map((f) => ({ ...f, enabled: true, status: 'Active' })));
  };

  const disableAll = () => {
    setFeatures((prev) => prev.map((f) => ({ ...f, enabled: false, status: 'Disabled' })));
  };

  const resetFeatures = () => {
    setFeatures((prev) =>
      prev.map((f) => ({
        ...f,
        enabled: f.id !== 'hhgkt_graph' && f.id !== 'contradiction_probe' && f.id !== 'cpf_scoring' && f.id !== 'question_dedup' && f.id !== 'report_generation',
        status: f.id === 'cpf_scoring' ? 'Pending' : (f.id === 'hhgkt_graph' || f.id === 'contradiction_probe' || f.id === 'question_dedup' || f.id === 'report_generation' ? 'Disabled' : 'Active')
      }))
    );
  };

  // Pipeline stages from screenshot
  const pipelineStages = [
    { id: 'ws', label: 'WebSocket Connect', status: 'done' },
    { id: 'audio', label: 'Audio Input', status: 'done' },
    { id: 'transcribe', label: 'Transcription', status: 'done' },
    { id: 'question', label: 'Question Generation', status: 'done' },
    { id: 'response', label: 'Candidate Response', status: pipelineStatus.candidateResponse || 'active' },
    { id: 'eval', label: 'Shadow Evaluation', status: pipelineStatus.shadowEval || 'pending' },
    { id: 'bkt', label: 'BKT Update', status: pipelineStatus.bkt || 'pending' },
    { id: 'mirt', label: 'MIRT Update', status: pipelineStatus.mirt || 'pending' },
    { id: 'policy', label: 'Policy Router', status: pipelineStatus.policy || 'pending' }
  ];

  return (
    <div className="live-grid">
      {/* =========================================================================
          COLUMN 1: Interview Stage & Dialogue + Pipeline + Debug Tabs
          ========================================================================= */}
      <div className="interview-stage-col">
        {/* Alex Interviewer Card */}
        <div className="dashboard-card">
          <div className="alex-interviewer-header">
            <div className="alex-profile">
              <div className="alex-avatar-circle">
                <Bot size={24} />
              </div>
              <div>
                <div className="alex-name">Alex</div>
                <div className="alex-role">AI Interviewer</div>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div className="audio-waveform-container">
                <div className="wave-bar" />
                <div className="wave-bar" />
                <div className="wave-bar" />
                <div className="wave-bar" />
                <div className="wave-bar" />
                <div className="wave-bar" />
                <div className="wave-bar" />
                <div className="wave-bar" />
              </div>
              <div className="pill-status green">
                <div className="status-dot-pulse" style={{ width: 6, height: 6 }} />
                <span>{isAlexSpeaking ? 'Speaking...' : 'Listening...'}</span>
              </div>
            </div>
          </div>

          {/* Dialogue Transcript Thread */}
          <div className="dialogue-thread" ref={chatScrollRef}>
            {conversationHistory.map((item, idx) => {
              if (item.type === 'ai') {
                return (
                  <div key={idx} className="bubble-ai">
                    <div className="bubble-ai-avatar">
                      <Bot size={16} />
                    </div>
                    <div className="bubble-ai-body">
                      <div className="bubble-ai-title">Alex (AI Interviewer)</div>
                      <div className="bubble-text">{item.text}</div>
                      <div className="bubble-timestamp">{item.time}</div>
                    </div>
                  </div>
                );
              } else if (item.type === 'candidate') {
                return (
                  <div key={idx} className="bubble-candidate">
                    <div className="bubble-candidate-title">You (Candidate)</div>
                    <div className="bubble-text">{item.text}</div>
                    <div className="bubble-timestamp">{item.time}</div>
                  </div>
                );
              } else if (item.type === 'shadow_eval') {
                return (
                  <div key={idx} className="shadow-eval-banner">
                    <div className="shadow-eval-header">
                      <div className="shadow-eval-title-wrap">
                        <div className="shadow-icon-box">
                          <Sparkles size={14} />
                        </div>
                        <div>
                          <div className="shadow-eval-name">Shadow Evaluator</div>
                          <div className="shadow-eval-desc">
                            {item.summary || 'Processing response... Analyzing for rubric match, depth, and skills.'}
                          </div>
                        </div>
                      </div>
                      <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--purple)' }}>
                        {item.progress || '68%'}
                      </span>
                    </div>
                    <div className="progress-track">
                      <div
                        className="progress-fill-purple"
                        style={{ width: item.progress || '68%' }}
                      />
                    </div>
                  </div>
                );
              }
              return null;
            })}
          </div>

          {/* Candidate Input Bar */}
          <form className="candidate-input-bar" onSubmit={handleSend}>
            <button
              type="button"
              className={`btn-mic ${isRecordingMic ? 'recording' : ''}`}
              onClick={onToggleMic}
              title={isRecordingMic ? 'Stop microphone' : 'Start microphone'}
            >
              <Mic size={18} />
            </button>
            <input
              type="text"
              className="candidate-text-input"
              placeholder="Type a test message..."
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
            />
            <button type="submit" className="btn btn-primary" style={{ padding: '9px 18px' }}>
              <Send size={15} />
              <span>Send</span>
            </button>
          </form>
        </div>

        {/* Session Pipeline Ribbon */}
        <div className="dashboard-card pipeline-card">
          <div className="card-heading-sm">
            <span>Session Pipeline</span>
          </div>
          <div className="pipeline-nodes-row">
            {pipelineStages.map((stage, idx) => (
              <React.Fragment key={stage.id}>
                <div className="pipeline-node">
                  <div className={`node-icon-circle ${stage.status}`}>
                    {stage.status === 'done' ? (
                      <CheckCircle2 size={14} />
                    ) : stage.status === 'active' ? (
                      <Activity size={14} />
                    ) : (
                      <Clock size={14} />
                    )}
                  </div>
                  <div className="node-label">{stage.label}</div>
                  <span className={`node-status-badge ${stage.status}`}>
                    {stage.status === 'done'
                      ? 'Done'
                      : stage.status === 'active'
                      ? 'In Progress'
                      : 'Pending'}
                  </span>
                </div>
                {idx < pipelineStages.length - 1 && <div className="pipeline-connector" />}
              </React.Fragment>
            ))}
          </div>
        </div>

        {/* Bottom Debug Tabs & Monospace Table */}
        <div className="dashboard-card" style={{ padding: '12px 16px' }}>
          <div className="debug-tabs-bar">
            {[
              { id: 'system', label: 'System Logs' },
              { id: 'websocket', label: 'WebSocket Events' },
              { id: 'transcript', label: 'Transcript / STT' },
              { id: 'shadow', label: 'Shadow Evaluator Output' },
              { id: 'scoring', label: 'Scoring & Mastery' },
              { id: 'db', label: 'Database Events' }
            ].map((tab) => (
              <button
                key={tab.id}
                className={`debug-tab ${activeDebugTab === tab.id ? 'active' : ''}`}
                onClick={() => setActiveDebugTab(tab.id)}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div className="log-table-container">
            <table className="log-table">
              <thead>
                <tr>
                  <th style={{ width: 80 }}>Time</th>
                  <th style={{ width: 70 }}>Severity</th>
                  <th style={{ width: 100 }}>Component</th>
                  <th>Message</th>
                </tr>
              </thead>
              <tbody>
                {debugLogs.map((log, idx) => (
                  <tr key={idx}>
                    <td style={{ color: 'var(--muted)' }}>{log.time}</td>
                    <td>
                      <span className={`log-tag-${log.severity.toLowerCase()}`}>
                        {log.severity}
                      </span>
                    </td>
                    <td style={{ color: 'var(--text)' }}>{log.component}</td>
                    <td style={{ color: 'var(--muted)' }}>{log.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* =========================================================================
          COLUMN 2: Real-time Activity & Session State & Scoring
          ========================================================================= */}
      <div className="middle-status-col">
        {/* Real-time Activity */}
        <div className="dashboard-card">
          <div className="card-heading-sm">
            <span>Real-time Activity</span>
          </div>
          <div className="activity-timeline">
            {activityTimeline.map((item, idx) => (
              <div key={idx} className="timeline-event-row">
                <div className="timeline-dot" />
                <span className="timeline-time">{item.time}</span>
                <span className="timeline-text">{item.text}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Session State & Scoring (Live) */}
        <div className="dashboard-card">
          <div className="card-heading-sm">
            <span>Session State & Scoring (Live)</span>
          </div>

          {/* 4 Mini State Chips */}
          <div className="state-chips-grid">
            <div className="state-chip-box">
              <div className="state-chip-label">Phase</div>
              <div className="state-chip-val">{telemetry.phase || 'DEEP_DIVE'}</div>
            </div>
            <div className="state-chip-box">
              <div className="state-chip-label">FSM State</div>
              <div className="state-chip-val">{telemetry.fsmState || 'QUESTION'}</div>
            </div>
            <div className="state-chip-box">
              <div className="state-chip-label">Role</div>
              <div className="state-chip-val" style={{ color: 'var(--text)' }}>
                {telemetry.role || 'Interviewer'}
              </div>
            </div>
            <div className="state-chip-box">
              <div className="state-chip-label">Skill Pillar</div>
              <div className="state-chip-val" style={{ fontSize: 12.5 }}>
                {telemetry.activeTopic || 'System Design'}
              </div>
            </div>
          </div>

          {/* Difficulty & BKT Mastery */}
          <div className="metric-row-split">
            <div>
              <div className="state-chip-label">Difficulty Level</div>
              <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--orange)' }}>
                {telemetry.difficulty || 'Medium'}
              </div>
            </div>
            <div style={{ width: '60%' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                <span className="state-chip-label">BKT Mastery</span>
                <span style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--blue)' }}>
                  {telemetry.bktMastery !== undefined ? telemetry.bktMastery : '0.72'}
                </span>
              </div>
              <div className="progress-track" style={{ height: 6 }}>
                <div
                  className="progress-fill-purple"
                  style={{
                    backgroundColor: 'var(--blue)',
                    width: `${Math.round((telemetry.bktMastery || 0.72) * 100)}%`
                  }}
                />
              </div>
            </div>
          </div>

          {/* MIRT Ability (5D) */}
          <div style={{ marginTop: 10 }}>
            <div className="state-chip-label" style={{ marginBottom: 6 }}>
              MIRT Ability (5D)
            </div>
            <div className="mirt-bars-container">
              {[
                { key: 'logic', label: 'Logic', val: telemetry.mirt?.logic ?? 0.68, color: 'var(--blue)' },
                { key: 'system', label: 'System', val: telemetry.mirt?.system_design ?? 0.61, color: 'var(--orange)' },
                { key: 'lang', label: 'Lang', val: telemetry.mirt?.language ?? 0.74, color: 'var(--green)' },
                { key: 'prob', label: 'Problem', val: telemetry.mirt?.problem_solving ?? 0.62, color: 'var(--red)' },
                { key: 'code', label: 'Code', val: telemetry.mirt?.coding ?? 0.58, color: 'var(--orange)' }
              ].map((dim) => (
                <div key={dim.key} className="mirt-bar-col">
                  <div className="mirt-bar-title">{dim.label}</div>
                  <div className="mirt-bar-track">
                    <div
                      className="mirt-bar-fill"
                      style={{
                        height: `${Math.round(dim.val * 100)}%`,
                        backgroundColor: dim.color
                      }}
                    />
                  </div>
                  <div className="mirt-bar-val" style={{ color: dim.color }}>
                    {dim.val.toFixed(2)}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Policy Directive & Master Score */}
          <div className="metric-row-split" style={{ marginTop: 6, marginBottom: 0 }}>
            <div>
              <div className="state-chip-label">Policy Directive</div>
              <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--blue)' }}>
                {telemetry.policyDirective || 'DEEPEN'}
              </div>
              <div style={{ fontSize: 10.5, color: 'var(--muted)' }}>
                Reason: Low depth score
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div className="state-chip-label">Master Score</div>
              <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--muted)' }}>
                {telemetry.masterScore || '—'}
              </div>
              <div style={{ fontSize: 10.5, color: 'var(--text-dim)' }}>(Not finalized)</div>
            </div>
          </div>
        </div>
      </div>

      {/* =========================================================================
          COLUMN 3: Feature Toggle Inspector
          ========================================================================= */}
      <div className="feature-inspector-col">
        <div className="dashboard-card" style={{ padding: '16px' }}>
          <div className="card-heading-sm" style={{ marginBottom: 8 }}>
            <span>Feature Toggle Inspector</span>
          </div>

          <div className="toggle-actions-header">
            <button className="btn-pill-action blue" onClick={enableAll}>
              Enable All
            </button>
            <button className="btn-pill-action" onClick={disableAll}>
              Disable All
            </button>
            <button className="btn-pill-action" onClick={resetFeatures}>
              Reset to Defaults
            </button>
          </div>

          <div style={{ maxHeight: '680px', overflowY: 'auto' }}>
            <table className="feature-toggle-table">
              <thead>
                <tr>
                  <th style={{ width: 44 }}></th>
                  <th>Feature / Engine</th>
                  <th>Description</th>
                  <th style={{ width: 80, textAlign: 'right' }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {features.map((feat) => {
                  const statusColor =
                    feat.status === 'Active'
                      ? 'green'
                      : feat.status === 'Pending'
                      ? 'orange'
                      : 'red';

                  return (
                    <tr key={feat.id}>
                      <td>
                        <label className="switch">
                          <input
                            type="checkbox"
                            checked={feat.enabled}
                            onChange={() => toggleFeature(feat.id)}
                          />
                          <span className="slider" />
                        </label>
                      </td>
                      <td>
                        <div className="feature-name-cell">{feat.name}</div>
                      </td>
                      <td>
                        <div className="feature-desc-cell">{feat.description}</div>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <span
                          className={`pill-status ${statusColor}`}
                          style={{ padding: '2px 8px', fontSize: 11 }}
                        >
                          ● {feat.status}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
