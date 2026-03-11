import { createClient } from "@supabase/supabase-js";

const supabaseUrl = "https://mmgwetvuilezqazwjtro.supabase.co";
const supabaseKey = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1tZ3dldHZ1aWxlenFhendqdHJvIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3Mjc3MDUwMSwiZXhwIjoyMDg4MzQ2NTAxfQ.fooiWG27FheHZRLeA9miGpFemC6z9GEC4TAiGrMIlbY";
const supabase = createClient(supabaseUrl, supabaseKey);

async function test() {
  console.log("Testing signInWithPassword...");
  const loginRes = await supabase.auth.signInWithPassword({
    email: 'hello@gmail.com',
    password: 'password123'
  });
  console.log("Login result:", loginRes.error ? loginRes.error.message : "Success");

  console.log("\nTesting signUp...");
  const signupRes = await supabase.auth.signUp({
    email: 'hello@gmail.com',
    password: 'password123'
  });
  console.log("Signup result:", signupRes.error ? signupRes.error.message : "Success");
}

test();
