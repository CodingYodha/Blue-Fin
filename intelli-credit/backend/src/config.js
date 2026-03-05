require("dotenv").config();

const config = {
  port: process.env.PORT || 3001,
  supabaseUrl: process.env.SUPABASE_URL,
  supabaseServiceKey: process.env.SUPABASE_SERVICE_KEY,
  goServiceUrl: process.env.GO_SERVICE_URL || "http://localhost:8081",
  aiServiceUrl: process.env.AI_SERVICE_URL || "http://localhost:8000",
  sharedTmpPath: process.env.SHARED_TMP_PATH || "./tmp/intelli-credit",
};

module.exports = config;
