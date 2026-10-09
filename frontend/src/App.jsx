import React, { useState, useEffect, useRef } from 'react';
import Sidebar from './components/layout/Sidebar';
import Topbar from './components/layout/Topbar';
import LiveInterview from './pages/LiveInterview';
import FeatureControls from './pages/FeatureControls';
import SystemLogs from './pages/SystemLogs';
import EngineAnalytics from './pages/EngineAnalytics';
import ReportsView from './pages/ReportsView';
import SettingsView from './pages/SettingsView';
import { INITIAL_FEATURES, INITIAL_LOGS, INITIAL_TIMELINE } from './data/mockData';
import { InterviewWebSocket } from './services/websocketService';
import './styles/global.css';

export default function App() {
  const [activeNav, setActiveNav] = useState('live');
  const [features, setFeatures] = useState(INITIAL_FEATURES);
  const [debugLogs, setDebugLogs] = useState(INITIAL_LOGS);
  const [activityTimeline, setActivityTimeline] = useState(INITIAL_TIMELINE);

  // Session State
  const [sessionId, setSessionId] = useState('sess_2025_09_30_1745_001');
  const [candidateName, setCandidateName] = useState('Candidate');
  const [isWsConnected, setIsWsConnected] = useState(false);
  const [wsLatency, setWsLatency] = useState('—');
  const [isInterviewRunning, setIsInterviewRunning] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [durationSeconds, setDurationSeconds] = useState(0);
  const [isAlexSpeaking, setIsAlexSpeaking] = useState(false);
  const [isRecordingMic, setIsRecordingMic] = useState(false);
  const [isInterrupted, setIsInterrupted] = useState(false);

  // Dialogue Thread
  const [conversationHistory, setConversationHistory] = useState([
    {
      type: 'ai',
      text: 'Click "Start" in the top bar to begin your live technical interview with Alex.',
      time: '00:00'
    }
  ]);

  // Telemetry & Engines State
  const [telemetry, setTelemetry] = useState({
    phase: 'INTRO',
    fsmState: 'QUESTION',
    role: 'Interviewer',
    activeTopic: 'SYSTEM_DESIGN',
    difficulty: 'Medium',
    bktMastery: 0.40,
    mirt: {
      logic: 0.50,
      system_design: 0.50,
      language: 0.50,
      problem_solving: 0.50,
      coding: 0.50
    },
    policyDirective: 'EXPLORE',
    masterScore: '—'
  });

  const [pipelineStatus, setPipelineStatus] = useState({
    candidateResponse: 'pending',
    shadowEval: 'pending',
    bkt: 'pending',
    mirt: 'pending',
    policy: 'pending'
  });

  const wsClientRef = useRef(null);

  const formatDuration = (totalSeconds) => {
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  };

  const durationSecondsRef = useRef(0);
  useEffect(() => {
    durationSecondsRef.current = durationSeconds;
  }, [durationSeconds]);

  // Process incoming WebSocket events from live_server.py
  const handleIncomingWsMessage = (msg) => {
    if (!msg || !msg.event) return;

    const timeStr = formatDuration(durationSecondsRef.current);

    if (msg.event === 'session_started') {
      setSessionId(msg.session_id);
      setActivityTimeline((prev) => [
        ...prev,
        { time: timeStr, text: `Session started (${msg.session_id})` }
      ]);
    } else if (msg.event === 'candidate_name_updated') {
      if (msg.name) {
        setCandidateName(msg.name);
        setActivityTimeline((prev) => [
          ...prev,
          { time: timeStr, text: `Candidate identified as: ${msg.name}` }
        ]);
      }
    } else if (msg.event === 'ai_interrupted') {
      setIsAlexSpeaking(false);
      setIsInterrupted(true);
      setTimeout(() => setIsInterrupted(false), 2500);
      setActivityTimeline((prev) => [
        ...prev,
        { time: timeStr, text: 'Alex paused (candidate interrupted) — listening' }
      ]);
    } else if (msg.event === 'ai_turn_start') {
      setIsAlexSpeaking(true);
      setPipelineStatus((p) => ({ ...p, question: 'active' }));
      setConversationHistory((prev) => {
        const last = prev[prev.length - 1];
        if (last && last.type === 'ai' && last.isStreaming) return prev;
        return [...prev, { type: 'ai', text: '', time: timeStr, isStreaming: true }];
      });
    } else if (msg.event === 'ai_transcript_chunk') {
      setIsAlexSpeaking(true);
      // Append or update streaming AI message
      setConversationHistory((prev) => {
        const last = prev[prev.length - 1];
        if (last && last.type === 'ai') {
          return [
            ...prev.slice(0, -1),
            { ...last, text: last.text + msg.text, isStreaming: true }
          ];
        } else {
          return [...prev, { type: 'ai', text: msg.text, time: timeStr, isStreaming: true }];
        }
      });
    } else if (msg.event === 'turn_complete') {
      setIsAlexSpeaking(false);
      setConversationHistory((prev) => {
        const last = prev[prev.length - 1];
        if (last && last.type === 'ai') {
          return [...prev.slice(0, -1), { ...last, isStreaming: false }];
        }
        return prev;
      });
      setPipelineStatus((p) => ({ ...p, candidateResponse: 'active' }));
    } else if (msg.event === 'candidate_transcript_chunk') {
      // Real-time streaming candidate words from Gemini Live STT
      const chunkText = msg.text || '';
      if (!chunkText.trim()) return;
      setConversationHistory((prev) => {
        const last = prev[prev.length - 1];
        if (last && last.type === 'candidate' && last.isStreaming) {
          return [
            ...prev.slice(0, -1),
            { ...last, text: last.text + (last.text ? ' ' : '') + chunkText, isStreaming: true }
          ];
        } else {
          return [
            ...prev,
            { type: 'candidate', text: chunkText, time: timeStr, isStreaming: true }
          ];
        }
      });
    } else if (msg.event === 'candidate_transcript') {
      const finalText = msg.text || '';
      setConversationHistory((prev) => {
        const last = prev[prev.length - 1];
        const secondLast = prev[prev.length - 2];
        if (last && last.type === 'shadow_eval' && secondLast && secondLast.type === 'candidate') {
          // Already finalized by client silence detector, update candidate text if needed
          return [
            ...prev.slice(0, -2),
            { ...secondLast, text: finalText || secondLast.text, isStreaming: false },
            last
          ];
        }
        if (last && last.type === 'candidate') {
          return [
            ...prev.slice(0, -1),
            { ...last, text: finalText || last.text, isStreaming: false },
            { type: 'shadow_eval', progress: '65%', time: timeStr }
          ];
        } else {
          return [
            ...prev,
            { type: 'candidate', text: finalText, time: timeStr, isStreaming: false },
            { type: 'shadow_eval', progress: '65%', time: timeStr }
          ];
        }
      });
      setPipelineStatus({
        candidateResponse: 'done',
        shadowEval: 'active',
        bkt: 'pending',
        mirt: 'pending',
        policy: 'pending'
      });
      setActivityTimeline((prev) => [
        ...prev,
        { time: timeStr, text: 'Candidate answer submitted' },
        { time: timeStr, text: 'Shadow Evaluator grading response...' }
      ]);
    } else if (msg.event === 'shadow_eval_completed') {
      const depthPct = Math.round((msg.depth_score || 0.65) * 100);
      setConversationHistory((prev) =>
        prev.map((item) =>
          item.type === 'shadow_eval'
            ? {
                ...item,
                progress: `${depthPct}%`,
                obs: msg.observation,
                depth: depthPct,
                summary: msg.summary || `Observation: ${msg.observation} | Depth: ${depthPct}%`
              }
            : item
        )
      );
      setActivityTimeline((prev) => [
        ...prev,
        { time: timeStr, text: `Shadow Evaluator: Obs=${msg.observation}, Depth=${depthPct}%` }
      ]);
      setPipelineStatus((p) => ({ ...p, shadowEval: 'done', bkt: 'active' }));
    } else if (msg.event === 'policy_directive_selected') {
      setTelemetry((prev) => ({
        ...prev,
        policyDirective: msg.action,
        fsmState: msg.fsm_state
      }));
      setActivityTimeline((prev) => [
        ...prev,
        { time: timeStr, text: `Policy Router: ${msg.action} (${msg.fsm_state})` }
      ]);
      setPipelineStatus((p) => ({ ...p, bkt: 'done', mirt: 'done', policy: 'done' }));
    } else if (msg.event === 'telemetry_update' && msg.telemetry) {
      const t = msg.telemetry;
      setTelemetry((prev) => ({
        ...prev,
        bktMastery: t.bkt_mastery !== undefined ? t.bkt_mastery : prev.bktMastery,
        activeTopic: t.active_topic || t.current_skill || prev.activeTopic,
        phase: t.session_phase || prev.phase,
        fsmState: t.fsm_state || prev.fsmState,
        policyDirective: t.policy_directive || prev.policyDirective,
        difficulty: t.difficulty || prev.difficulty,
        mirt: t.mirt_radar
          ? {
              logic: t.mirt_radar.algorithms ?? 0.68,
              system_design: t.mirt_radar.system_design ?? 0.61,
              language: t.mirt_radar.concurrency ?? 0.74,
              problem_solving: t.mirt_radar.databases ?? 0.62,
              coding: t.mirt_radar.distributed_systems ?? 0.58
            }
          : prev.mirt
      }));

      // Add to activity timeline
      if (msg.active_module) {
        setActivityTimeline((prev) => [
          ...prev,
          { time: timeStr, text: `${msg.active_module} updated telemetry` }
        ]);
      }
    } else if (msg.event === 'reports_generated') {
      setTelemetry((prev) => ({ ...prev, masterScore: msg.hiring_verdict || 'HIRE' }));
      setActivityTimeline((prev) => [
        ...prev,
        { time: timeStr, text: `Final Dual Assessment Reports generated: ${msg.hiring_verdict}` }
      ]);
    }
  };

  // Format Duration timer mm:ss
  useEffect(() => {
    let timer;
    if (isInterviewRunning && !isPaused) {
      timer = setInterval(() => {
        setDurationSeconds((s) => s + 1);
      }, 1000);
    }
    return () => clearInterval(timer);
  }, [isInterviewRunning, isPaused]);

  // Connect on Mount or on Demand
  useEffect(() => {
    const ws = new InterviewWebSocket({
      onStatusChange: ({ connected, latency }) => {
        setIsWsConnected(connected);
        setWsLatency(latency);
      },
      onAudioPlayState: (isPlaying) => {
        setIsAlexSpeaking(isPlaying);
      },
      onCandidateSpeechChunk: (text, isFinal) => {
        if (!text) return;
        const timeStr = formatDuration(durationSecondsRef.current);
        setConversationHistory((prev) => {
          const last = prev[prev.length - 1];
          if (last && last.type === 'candidate' && last.isStreaming) {
            return [
              ...prev.slice(0, -1),
              { ...last, text: text, isStreaming: !isFinal }
            ];
          } else if (last && last.type === 'candidate' && !isFinal) {
            return [
              ...prev.slice(0, -1),
              { ...last, text: text, isStreaming: true }
            ];
          } else {
            return [
              ...prev,
              { type: 'candidate', text: text, time: timeStr, isStreaming: !isFinal }
            ];
          }
        });
      },
      onCandidateSpeechFinal: (text) => {
        if (!text || !text.trim()) return;
        const timeStr = formatDuration(durationSecondsRef.current);
        setConversationHistory((prev) => {
          const last = prev[prev.length - 1];
          if (last && last.type === 'candidate') {
            return [
              ...prev.slice(0, -1),
              { ...last, text: text, isStreaming: false },
              { type: 'shadow_eval', progress: '65%', time: timeStr }
            ];
          } else {
            return [
              ...prev,
              { type: 'candidate', text: text, time: timeStr, isStreaming: false },
              { type: 'shadow_eval', progress: '65%', time: timeStr }
            ];
          }
        });
        setPipelineStatus({
          candidateResponse: 'done',
          shadowEval: 'active',
          bkt: 'pending',
          mirt: 'pending',
          policy: 'pending'
        });
        setActivityTimeline((prev) => [
          ...prev,
          { time: timeStr, text: 'Candidate finished speaking (silence detected)' },
          { time: timeStr, text: 'Shadow Evaluator grading in background...' }
        ]);
      },
      onMessage: (msg) => {
        handleIncomingWsMessage(msg);
      }
    });

    wsClientRef.current = ws;

    return () => {
      ws.disconnect();
    };
  }, []);

  // Handle Candidate text input
  const handleSendCandidateMessage = (text) => {
    const timeStr = formatDuration(durationSeconds);
    // Send to real WebSocket
    if (wsClientRef.current && wsClientRef.current.isConnected) {
      wsClientRef.current.sendCandidateText(text);
    } else {
      // Local fallback simulation
      setConversationHistory((prev) => [
        ...prev,
        { type: 'candidate', text, time: timeStr },
        { type: 'shadow_eval', progress: '78%', time: timeStr }
      ]);

      setActivityTimeline((prev) => [
        ...prev,
        { time: timeStr, text: `Candidate answer received: "${text.substring(0, 32)}..."` },
        { time: timeStr, text: 'Shadow Evaluator started' },
        { time: timeStr, text: 'BKT posterior updated: 0.78' }
      ]);

      setDebugLogs((prev) => [
        ...prev,
        { time: new Date().toLocaleTimeString(), severity: 'INFO', component: 'stt', message: `Candidate input: ${text}` },
        { time: new Date().toLocaleTimeString(), severity: 'INFO', component: 'shadow', message: 'Observation: 1 (Positive), Depth: 74%' }
      ]);

      setPipelineStatus({
        candidateResponse: 'done',
        shadowEval: 'done',
        bkt: 'done',
        mirt: 'done',
        policy: 'done'
      });
    }
  };

  const handleToggleMic = async () => {
    if (!isRecordingMic) {
      if (wsClientRef.current && wsClientRef.current.isConnected) {
        const ok = await wsClientRef.current.startMicrophone();
        if (ok) setIsRecordingMic(true);
      } else {
        setIsRecordingMic(true);
      }
    } else {
      if (wsClientRef.current && wsClientRef.current.isConnected) {
        wsClientRef.current.stopMicrophone();
      }
      setIsRecordingMic(false);
    }
  };

  const handleStartSession = async () => {
    setIsInterviewRunning(true);
    setIsPaused(false);
    setDurationSeconds(0);
    setConversationHistory([]);
    setActivityTimeline([
      { time: '00:00', text: 'Interview session starting (Hands-free mode)...' },
      { time: '00:00', text: 'Connecting to Alex (Gemini Live)...' }
    ]);
    if (wsClientRef.current) {
      wsClientRef.current.connect('', 'HARD');
      // Automatically activate microphone for completely hands-free voice conversation
      const micOk = await wsClientRef.current.startMicrophone();
      if (micOk) {
        setIsRecordingMic(true);
        setActivityTimeline((prev) => [
          ...prev,
          { time: '00:00', text: 'Microphone active — hands-free voice mode enabled' }
        ]);
      }
    }
  };

  const handlePauseSession = () => {
    if (isPaused) {
      setIsPaused(false);
      wsClientRef.current?.resume();
    } else {
      setIsPaused(true);
      wsClientRef.current?.pause();
    }
  };

  const handleEndSession = () => {
    setIsInterviewRunning(false);
    setIsRecordingMic(false);
    wsClientRef.current?.stopMicrophone();
    wsClientRef.current?.finish();
  };

  return (
    <div className="app-container">
      {/* 250px Fixed Sidebar */}
      <Sidebar
        activeNav={activeNav}
        setActiveNav={setActiveNav}
        isWsConnected={isWsConnected}
        latency={wsLatency}
      />

      {/* Main Content Area */}
      <div className="main-wrapper">
        <Topbar
          sessionId={sessionId}
          candidateName={candidateName}
          isWsConnected={isWsConnected}
          duration={formatDuration(durationSeconds)}
          isInterviewRunning={isInterviewRunning}
          isPaused={isPaused}
          onStart={handleStartSession}
          onPause={handlePauseSession}
          onEnd={handleEndSession}
        />

        <main className="content-body">
          {activeNav === 'live' && (
            <LiveInterview
              features={features}
              setFeatures={setFeatures}
              onSendCandidateMessage={handleSendCandidateMessage}
              onToggleMic={handleToggleMic}
              isRecordingMic={isRecordingMic}
              conversationHistory={conversationHistory}
              activityTimeline={activityTimeline}
              pipelineStatus={pipelineStatus}
              telemetry={telemetry}
              debugLogs={debugLogs}
              isAlexSpeaking={isAlexSpeaking}
              candidateName={candidateName}
              isInterrupted={isInterrupted}
            />
          )}

          {activeNav === 'features' && (
            <FeatureControls
              features={features}
              setFeatures={setFeatures}
            />
          )}

          {activeNav === 'logs' && <SystemLogs defaultLogs={debugLogs} />}

          {activeNav === 'analytics' && <EngineAnalytics telemetry={telemetry} />}

          {activeNav === 'reports' && <ReportsView />}

          {activeNav === 'settings' && <SettingsView isWsConnected={isWsConnected} />}
        </main>
      </div>
    </div>
  );
}
