import { createClient } from "@supabase/supabase-js";
import config from "../config.js";

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
export default new Proxy(
  {},
  {
    get(_, prop) {
      return getClient()[prop];
    },
  },
);
