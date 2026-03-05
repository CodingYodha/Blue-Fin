const fs = require("fs");
const config = require("../config");

function setupTmp() {
  fs.mkdirSync(config.sharedTmpPath, { recursive: true });
  console.log("Shared tmp directory ready:", config.sharedTmpPath);
}

module.exports = setupTmp;
