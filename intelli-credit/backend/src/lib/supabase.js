const { createClient } = require("@supabase/supabase-js");
const config = require("../config");

let supabase = null;

function getClient() {
  if (!supabase) {
    if (
      !config.supabaseUrl ||
      config.supabaseUrl === "your_supabase_url_here"
    ) {
      throw new Error("SUPABASE_URL is not configured in .env");
    }
    supabase = createClient(config.supabaseUrl, config.supabaseServiceKey);
  }
  return supabase;
}

// Proxy so callers can do `supabase.from(...)` directly
module.exports = new Proxy(
  {},
  {
    get(_, prop) {
      return getClient()[prop];
    },
  },
);
