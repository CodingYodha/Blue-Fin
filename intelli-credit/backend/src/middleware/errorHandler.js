export default async function errorHandler(c, next) {
  try {
    await next();
  } catch (err) {
    const ts = new Date().toISOString();
    const path = c.req.path;
    console.error(`[${ts}] Unhandled error at ${path}:`, err);
    return c.json(
      { error: err.message || "Internal server error", status: 500, path },
      500,
    );
  }
}
