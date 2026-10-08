/**
 * API Service for FastAPI backend integration
 */

export async function fetchServerLogs(limit = 100) {
  try {
    const res = await fetch(`/api/logs?limit=${limit}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return data.lines || [];
  } catch (err) {
    console.warn("Could not fetch logs from FastAPI backend:", err.message);
    return null;
  }
}

export async function fetchAllReports() {
  try {
    const res = await fetch("/api/reports");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return data.reports || [];
  } catch (err) {
    console.warn("Could not fetch reports from FastAPI backend:", err.message);
    return [];
  }
}

export async function fetchCompactedCards(sessionId) {
  try {
    const res = await fetch(`/api/session/${sessionId}/compacted-cards`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return data.cards || [];
  } catch (err) {
    console.warn(`Could not fetch cards for session ${sessionId}:`, err.message);
    return [];
  }
}

export async function checkBackendHealth() {
  try {
    const res = await fetch("/health");
    if (!res.ok) return false;
    const data = await res.json();
    return data.status === "healthy";
  } catch {
    return false;
  }
}
