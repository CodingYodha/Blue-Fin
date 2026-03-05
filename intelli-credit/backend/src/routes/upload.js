const { Hono } = require("hono");
const multer = require("multer");
const path = require("path");
const supabase = require("../lib/supabase");
const { getJob, updateJobStatus } = require("../services/jobService");
const {
  saveFileToDisk,
  uploadToSupabase,
} = require("../services/storageService");

const ALLOWED_EXTENSIONS = [".pdf", ".csv", ".xlsx"];
const MAX_FILE_SIZE = 20 * 1024 * 1024; // 20MB

const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: MAX_FILE_SIZE },
});

const uploadFields = upload.fields([
  { name: "annual_report", maxCount: 1 },
  { name: "gst_filing", maxCount: 1 },
  { name: "bank_statement", maxCount: 1 },
  { name: "itr", maxCount: 1 },
  { name: "mca", maxCount: 1 },
]);

const router = new Hono();

router.post("/:jobId", async (c) => {
  const jobId = c.req.param("jobId");

  const job = await getJob(jobId);
  if (!job) return c.json({ error: "Job not found" }, 404);

  // Use raw node req/res for multer
  const nodeReq = c.env.incoming;
  const nodeRes = c.env.outgoing;

  try {
    const files = await new Promise((resolve, reject) => {
      uploadFields(nodeReq, nodeRes, (err) => {
        if (err) return reject(err);
        resolve(nodeReq.files || {});
      });
    });

    const received = [];

    for (const [fieldname, fileArr] of Object.entries(files)) {
      const file = fileArr[0];
      const ext = path.extname(file.originalname).toLowerCase();

      if (!ALLOWED_EXTENSIONS.includes(ext)) {
        return c.json(
          { error: `Invalid file type: ${file.originalname}` },
          400,
        );
      }

      const savedPath = saveFileToDisk(jobId, file.buffer, file.originalname);
      const storagePath = await uploadToSupabase(
        jobId,
        savedPath,
        file.originalname,
      );

      await supabase.from("uploaded_files").insert({
        job_id: jobId,
        file_type: fieldname,
        original_name: file.originalname,
        storage_path: storagePath,
        file_size: file.size,
      });

      received.push(fieldname);
    }

    await updateJobStatus(jobId, "processing", null);

    return c.json({ success: true, job_id: jobId, files_received: received });
  } catch (err) {
    return c.json({ error: err.message }, 400);
  }
});

module.exports = router;
