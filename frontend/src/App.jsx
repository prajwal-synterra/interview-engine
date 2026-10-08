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
  const [isWsConnected, setIsWsConnected] = useState(true);
  const [wsLatency, setWsLatency] = useState('0.8ms');
  const [isInterviewRunning, setIsInterviewRunning] = useState(true);
  const [isPaused, setIsPaused] = useState(false);
  const [durationSeconds, setDurationSeconds] = useState(272); // 04:32
  const [isAlexSpeaking, setIsAlexSpeaking] = useState(false);

  // Dialogue Thread
  const [conversationHistory, setConversationHistory] = useState([
    {
      type: 'ai',
      text: 'How would you design a scalable real-time chat application?',
      time: '04:12'
    },
    {
      type: 'candidate',
      text: 'I would use WebSockets for bidirectional communication and a load balancer to distribute connections.',
      time: '04:28'
    },
    {
      type: 'shadow_eval',
      progress: '68%',
      time: '04:30'
    }
  ]);

  // Telemetry & Engines State
  const [telemetry, setTelemetry] = useState({
    phase: 'DEEP_DIVE',
    fsmState: 'QUESTION',
    role: 'Interviewer',
    activeTopic: 'System Design',
    difficulty: 'Medium',
    bktMastery: 0.72,
    mirt: {
      logic: 0.68,
      system_design: 0.61,
      language: 0.74,
      problem_solving: 0.62,
      coding: 0.58
    },
    policyDirective: 'DEEPEN',
    masterScore: '—'
  });

  const [pipelineStatus, setPipelineStatus] = useState({
    candidateResponse: 'active',
    shadowEval: 'pending',
    bkt: 'pending',
    mirt: 'pending',
    policy: 'pending'
  });

  const wsClientRef = useRef(null);

  // Initialize WebSocket connection to FastAPI
  useEffect(() => {
    const ws = new InterviewWebSocket({
      onStatusChange: ({ connected, latency }) => {
        setIsWsConnected(connected);
        setWsLatency(latency);
      },
      onMessage: (msg) => {
        handleIncomingWsMessage(msg);
      }
    });

    ws.connect('Alex Vance', 'HARD');
    wsClientRef.current = ws;

    return () => {
      ws.disconnect();
    };
  }, []);

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

  const formatDuration = (totalSeconds) => {
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  };

  // Process incoming WebSocket events from live_server.py
  const handleIncomingWsMessage = (msg) => {
    if (!msg || !msg.event) return;

    const timeStr = formatDuration(durationSeconds);

    if (msg.event === 'session_started') {
      setSessionId(msg.session_id);
    } else if (msg.event === 'ai_turn_start') {
      setIsAlexSpeaking(true);
    } else if (msg.event === 'ai_transcript_chunk') {
      setIsAlexSpeaking(true);
      // Append or update last AI message
      setConversationHistory((prev) => {
        const last = prev[prev.length - 1];
        if (last && last.type === 'ai') {
          return [
            ...prev.slice(0, -1),
            { ...last, text: last.text + msg.text }
          ];
        } else {
          return [...prev, { type: 'ai', text: msg.text, time: timeStr }];
        }
      });
    } else if (msg.event === 'turn_complete') {
      setIsAlexSpeaking(false);
      setPipelineStatus((p) => ({ ...p, candidateResponse: 'active' }));
    } else if (msg.event === 'candidate_transcript') {
      setConversationHistory((prev) => [
        ...prev,
        { type: 'candidate', text: msg.text, time: timeStr },
        { type: 'shadow_eval', progress: '85%', time: timeStr }
      ]);
      setPipelineStatus({
        candidateResponse: 'done',
        shadowEval: 'active',
        bkt: 'pending',
        mirt: 'pending',
        policy: 'pending'
      });
    } else if (msg.event === 'telemetry_update' && msg.telemetry) {
      const t = msg.telemetry;
      setTelemetry((prev) => ({
        ...prev,
        bktMastery: t.bkt_mastery ?? prev.bktMastery,
        activeTopic: t.active_topic ?? prev.activeTopic,
        phase: t.session_phase ?? prev.phase,
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
    }
  };

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

  const handleStartSession = () => {
    setIsInterviewRunning(true);
    setIsPaused(false);
    if (wsClientRef.current) {
      wsClientRef.current.connect('Alex Vance', 'HARD');
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
              conversationHistory={conversationHistory}
              activityTimeline={activityTimeline}
              pipelineStatus={pipelineStatus}
              telemetry={telemetry}
              debugLogs={debugLogs}
              isAlexSpeaking={isAlexSpeaking}
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
