/**
 * WebSocket Service for real-time interview interaction with FastAPI live server
 */

export class InterviewWebSocket {
  constructor({ onMessage, onStatusChange }) {
    this.ws = null;
    this.onMessage = onMessage || (() => {});
    this.onStatusChange = onStatusChange || (() => {});
    this.isConnected = false;
  }

  connect(candidateName = "Candidate", tier = "HARD") {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    // If running in Vite dev server (port 5173), connect directly to backend port 8000 or via proxy
    const host = window.location.port === "5173" ? "127.0.0.1:8000" : window.location.host;
    const wsUrl = `${protocol}//${host}/ws/interview`;

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        this.isConnected = true;
        this.onStatusChange({ connected: true, latency: "0.8ms" });
        // Initial handshake
        this.sendJson({ name: candidateName, level: tier });
      };

      this.ws.onmessage = (event) => {
        if (typeof event.data === "string") {
          try {
            const data = JSON.parse(event.data);
            this.onMessage(data);
          } catch {
            this.onMessage({ event: "raw_text", text: event.data });
          }
        }
      };

      this.ws.onclose = () => {
        this.isConnected = false;
        this.onStatusChange({ connected: false, latency: "—" });
      };

      this.ws.onerror = (err) => {
        console.warn("WebSocket error:", err);
        this.isConnected = false;
        this.onStatusChange({ connected: false, latency: "Error" });
      };
    } catch (e) {
      console.warn("Could not open WebSocket:", e);
      this.onStatusChange({ connected: false, latency: "Failed" });
    }
  }

  sendJson(payload) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(payload));
    }
  }

  sendCandidateText(text) {
    this.sendJson({
      action: "candidate_text",
      transcript: text
    });
  }

  pause() {
    this.sendJson({ action: "pause_interview" });
  }

  resume() {
    this.sendJson({ action: "resume_interview" });
  }

  finish() {
    this.sendJson({ action: "finish_interview" });
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.isConnected = false;
    this.onStatusChange({ connected: false, latency: "—" });
  }
}
