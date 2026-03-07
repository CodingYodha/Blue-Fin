import { v4 as uuidv4 } from "uuid";
import supabase from "./src/lib/supabase.js";
async function check() {
  const testId = uuidv4();
  const { data, error } = await supabase.from('jobs').insert({ id: testId, company_name: 'test', status: 'pending' }).select().single();
  if (error) console.error("Error inserting job:", error);
  else console.log("Jobs row:", Object.keys(data));
  await supabase.from('jobs').delete().eq('id', testId);
}
check();
