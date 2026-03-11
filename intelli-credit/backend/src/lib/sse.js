// Manages active SSE connections: jobId -> res
const connections = new Map();

// Heartbeat intervals: jobId -> interval
const heartbeats = new Map();

export function registerConnection(jobId, res) {
  // Close any existing connection for this job
  if (connections.has(jobId)) {
    clearInterval(heartbeats.get(jobId));
    heartbeats.delete(jobId);
  }

  connections.set(jobId, res);
  res.writeHead(200, {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
  });
  res.write(": connected\n\n");

  // Send heartbeat every 15s to keep connection alive
  const hb = setInterval(() => {
    if (connections.has(jobId)) {
      try { res.write(": heartbeat\n\n"); } catch (_) { clearInterval(hb); }
    } else {
      clearInterval(hb);
    }
  }, 15000);
  heartbeats.set(jobId, hb);

  // Clean up on client disconnect
  res.on("close", () => {
    clearInterval(heartbeats.get(jobId));
    heartbeats.delete(jobId);
    connections.delete(jobId);
  });
}

export function sendEvent(jobId, eventObj) {
  const res = connections.get(jobId);
  if (res) {
    res.write("data: " + JSON.stringify(eventObj) + "\n\n");
  }
}

export function closeConnection(jobId) {
  const res = connections.get(jobId);
  if (res) {
    res.end();
    connections.delete(jobId);
  }
  clearInterval(heartbeats.get(jobId));
  heartbeats.delete(jobId);
}
