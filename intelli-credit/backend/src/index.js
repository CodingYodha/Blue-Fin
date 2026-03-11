import { Hono } from "hono";
import { serve } from "@hono/node-server";
import { cors } from "hono/cors";
import config from "./config.js";
import errorHandler from "./middleware/errorHandler.js";
import setupTmp from "./lib/setupTmp.js";
import { handleSSEStream } from "./routes/analysis.js";
import {
  jobsRouter,
  uploadRouter,
  analysisRouter,
  officerRouter,
  camRouter,
  authRouter,
} from "./routes/index.js";

const app = new Hono();

// Global error handler — must be first
app.use("*", errorHandler);

// CORS - allow all origins so frontend on any port can connect
app.use("*", cors({ origin: "*" }));

// Routes
app.route("/api/auth", authRouter);
app.route("/api/jobs", jobsRouter);
app.route("/api/upload", uploadRouter);
app.route("/api/analysis", analysisRouter);
app.route("/api/officer", officerRouter);
app.route("/api/cam", camRouter);

app.get("/health", (c) => {
  return c.json({ status: "ok", timestamp: Date.now() });
});

// Ensure tmp directory exists before serving requests
setupTmp();

// Use createServer so we can intercept SSE requests before Hono
import { createServer } from "node:http";
import { getRequestListener } from "@hono/node-server";

const requestListener = getRequestListener(app.fetch);

const server = createServer(async (req, res) => {
  // Intercept SSE stream requests at the raw HTTP level — prevents Hono
  // from touching the response and causing ERR_HTTP_HEADERS_SENT.
  const sseMatch = req.url?.match(/^\/api\/analysis\/([^/]+)\/stream/);
  if (sseMatch) {
    // Set CORS headers for SSE (both preflight and actual request)
    res.setHeader("Access-Control-Allow-Origin", "*");
    res.setHeader("Access-Control-Allow-Credentials", "true");
    res.setHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
    res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization");

    // Handle CORS preflight
    if (req.method === "OPTIONS") {
      res.writeHead(204);
      res.end();
      return;
    }

    if (req.method === "GET") {
      try {
        await handleSSEStream(sseMatch[1], res);
      } catch (err) {
        console.error(`[SSE] Error in stream handler for ${sseMatch[1]}:`, err);
        if (!res.headersSent) {
          res.writeHead(500, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ error: "SSE handler error" }));
        }
      }
      return;
    }
  }
  // Everything else goes through Hono
  requestListener(req, res);
});

server.listen(config.port, () => {
  console.log(`INTELLI-CREDIT backend running on port ${config.port}`);
});
