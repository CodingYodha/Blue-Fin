import fs from "fs";
import config from "../config.js";

export default function setupTmp() {
  fs.mkdirSync(config.sharedTmpPath, { recursive: true });
  console.log("Shared tmp directory ready:", config.sharedTmpPath);
}
