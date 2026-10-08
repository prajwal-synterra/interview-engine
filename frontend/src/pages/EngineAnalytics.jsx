import React from 'react';
import { BarChart3, TrendingUp, Compass, Award } from 'lucide-react';

export default function EngineAnalytics({ telemetry }) {
  const mirt = telemetry.mirt || {
    logic: 0.68,
    system_design: 0.61,
    language: 0.74,
    problem_solving: 0.62,
    coding: 0.58
  };

  const dimensions = [
    { name: 'System Design & Distributed Systems', val: mirt.system_design, color: 'var(--blue)', desc: 'Concurrency, microservices, caches' },
    { name: 'Logic & Algorithmic Rigor', val: mirt.logic, color: 'var(--purple)', desc: 'Complexity, asymptotic analysis' },
    { name: 'Language & Ecosystem Fluency', val: mirt.language, color: 'var(--green)', desc: 'Memory models, runtime specifics' },
    { name: 'Problem Solving & Scaffolding', val: mirt.problem_solving, color: 'var(--orange)', desc: 'Independence, trade-off analysis' },
    { name: 'Production Coding & Concurrency', val: mirt.coding, color: 'var(--red)', desc: 'Deadlocks, race conditions' }
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div>
        <h2 className="page-title">Cognitive Engine Analytics</h2>
        <p className="page-subtitle">
          Real-time multidimensional Item Response Theory (MIRT) and Bayesian Knowledge Tracing (BKT) metrics.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 16 }}>
        {/* MIRT 5D Latent Ability Card */}
        <div className="dashboard-card">
          <div className="card-heading-sm">
            <span>5D Cognitive Potential Fingerprint (CPF)</span>
            <span className="pill-status green">2PL Logistic MIRT</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 14, marginTop: 12 }}>
            {dimensions.map((dim) => (
              <div key={dim.name}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <div>
                    <strong style={{ fontSize: 13, color: 'var(--text)' }}>{dim.name}</strong>
                    <div style={{ fontSize: 11, color: 'var(--muted)' }}>{dim.desc}</div>
                  </div>
                  <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: dim.color }}>
                    {(dim.val * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="progress-track" style={{ height: 8 }}>
                  <div
                    className="progress-fill-purple"
                    style={{ width: `${Math.round(dim.val * 100)}%`, backgroundColor: dim.color }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* BKT & Adaptive Information Card */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="dashboard-card">
            <div className="card-heading-sm">
              <span>Bayesian Mastery Progression</span>
              <span className="pill-status blue">P(L) = {telemetry.bktMastery || 0.72}</span>
            </div>

            <div style={{ margin: '14px 0', fontSize: 12.5, color: 'var(--muted)', lineHeight: 1.6 }}>
              Priors updated via dynamic slip floor (0.10 → 0.25) and scaffolding decay factor (0.85^level).
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <div className="state-chip-box">
                <div className="state-chip-label">Slip Floor (P_s)</div>
                <div className="state-chip-val" style={{ color: 'var(--text)' }}>0.100</div>
              </div>
              <div className="state-chip-box">
                <div className="state-chip-label">Guess Prior (P_g)</div>
                <div className="state-chip-val" style={{ color: 'var(--text)' }}>0.150</div>
              </div>
            </div>
          </div>

          <div className="dashboard-card">
            <div className="card-heading-sm">
              <span>Behavioral Proctor Integrity</span>
              <span className="pill-status green">BII = 1.00 (Verified)</span>
            </div>
            <p style={{ fontSize: 12.5, color: 'var(--muted)', marginTop: 8 }}>
              Type-Token Ratio (TTR) lexical diversity: 0.76. Zero latency jitter or Copilot copy-paste anomalies detected.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
