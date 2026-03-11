import { createClient } from "@supabase/supabase-js";
import fs from "fs";

// Load env vars
const envContent = fs.readFileSync(".env", "utf-8");
const envVars = envContent.split("\n").reduce((acc, line) => {
  const [key, ...value] = line.split("=");
  if (key && value.length) acc[key.trim()] = value.join("=").trim().replace(/"/g, "");
  return acc;
}, {});

const supabaseUrl = envVars.VITE_SUPABASE_URL || envVars.SUPABASE_URL;
const supabaseKey = envVars.SUPABASE_SERVICE_KEY || envVars.SUPABASE_KEY;

if (!supabaseUrl || !supabaseKey) {
  console.error("Missing Supabase credentials in .env");
  process.exit(1);
}

const supabase = createClient(supabaseUrl, supabaseKey);

async function checkCamStructure() {
  const { data, error } = await supabase
    .from("jobs")
    .select("id, company_name, result")
    .not("result", "is", null)
    .order("updated_at", { ascending: false })
    .limit(1);

  if (error) {
    console.error("Error fetching jobs:", error);
    process.exit(1);
  }

  if (data && data.length > 0) {
    console.log("Found Job:", data[0].id, data[0].company_name);
    console.log("Result object keys:", Object.keys(data[0].result));
    
    // Check CAM related data
    if (data[0].result.cam_sections) {
      console.log("cam_sections:", Object.keys(data[0].result.cam_sections));
    } else if (data[0].result.cam_report) {
       console.log("cam_report:", Object.keys(data[0].result.cam_report));
    } else if (data[0].result.sections) {
       console.log("sections:", Object.keys(data[0].result.sections));
    } else {
      console.log("No known CAM section keys found in result.");
      console.log("Full result snippet:", JSON.stringify(data[0].result, null, 2).substring(0, 500));
    }

  } else {
    console.log("No jobs with a result found.");
  }
}

checkCamStructure();
