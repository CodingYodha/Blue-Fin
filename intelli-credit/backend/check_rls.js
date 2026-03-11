import { createClient } from "@supabase/supabase-js";

const supabaseUrl = "https://mmgwetvuilezqazwjtro.supabase.co";
const supabaseKey = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1tZ3dldHZ1aWxlenFhendqdHJvIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3Mjc3MDUwMSwiZXhwIjoyMDg4MzQ2NTAxfQ.fooiWG27FheHZRLeA9miGpFemC6z9GEC4TAiGrMIlbY";
const supabase = createClient(supabaseUrl, supabaseKey);

async function checkRest() {
  // Let's just try to insert an audit log directly to see if RLS blocks it even with service key
  // Or query the table definitions if we can.
  console.log("Checking audit_log table visibility...");
  const { data, error } = await supabase.from("audit_log").select("*").limit(1);
  if (error) console.log("Audit log error:", error.message);
  else console.log("Audit log success. Found rows:", data.length);
  
  console.log("Attempting to insert into audit_log without service role...");
  const anonClient = createClient(supabaseUrl, "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1tZ3dldHZ1aWxlenFhendqdHJvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI3NzA1MDEsImV4cCI6MjA4ODM0NjUwMX0.2YI1l71w5H_o_rA-fF_7-F2F1-0c5tPZ0VpY9g7p4f8"); // Replace with anon key if known, else let's just use service role and turn OFF RLS?
  
}

checkRest();
