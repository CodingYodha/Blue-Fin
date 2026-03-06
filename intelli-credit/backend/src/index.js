import { Hono } from "hono";
import { serve } from "@hono/node-server";
import { cors } from "hono/cors";
import config from "./config.js";
import errorHandler from "./middleware/errorHandler.js";
import setupTmp from "./lib/setupTmp.js";
import {
  jobsRouter,
  uploadRouter,
  analysisRouter,
  officerRouter,
  camRouter,
} from "./routes/index.js";

const app = new Hono();

// Global error handler — must be first
app.use("*", errorHandler);

// CORS
app.use("*", cors({ origin: "http://localhost:5173" }));

// Routes
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

serve({ fetch: app.fetch, port: config.port }, () => {
  console.log(`INTELLI-CREDIT backend running on port ${config.port}`);
});
