// Manages active SSE connections: jobId -> res
const connections = new Map();

export function registerConnection(jobId, res) {
  connections.set(jobId, res);
  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache");
  res.setHeader("Connection", "keep-alive");
  res.write(": connected\n\n");
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
}
