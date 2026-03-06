import fs from "fs";
import path from "path";
import config from "../config.js";
import supabase from "../lib/supabase.js";

function saveFileToDisk(jobId, fileBuffer, filename) {
  const folderPath = path.join(config.sharedTmpPath, jobId);
  fs.mkdirSync(folderPath, { recursive: true });
  const filePath = path.join(folderPath, filename);
  fs.writeFileSync(filePath, fileBuffer);
  return filePath;
}

async function uploadToSupabase(jobId, filePath, fileName) {
  const fileBuffer = fs.readFileSync(filePath);
  const storagePath = `${jobId}/${fileName}`;

  const { error } = await supabase.storage
    .from("intelli-credit-uploads")
    .upload(storagePath, fileBuffer, { upsert: true });

  if (error) throw new Error(error.message);
  return storagePath;
}

export { saveFileToDisk, uploadToSupabase };
