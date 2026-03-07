import { Hono } from "hono";
import supabase from "../lib/supabase.js";

const router = new Hono();

router.post("/signup", async (c) => {
  try {
    const { email, password } = await c.req.json();
    if (!email || !password) {
      return c.json({ error: "Email and password are required" }, 400);
    }

    const { data, error } = await supabase.auth.signUp({
      email,
      password,
    });

    if (error) return c.json({ error: error.message }, 400);

    return c.json({ user: data.user, session: data.session });
  } catch (err) {
    return c.json({ error: err.message }, 500);
  }
});

router.post("/login", async (c) => {
  try {
    const { email, password } = await c.req.json();
    if (!email || !password) {
      return c.json({ error: "Email and password are required" }, 400);
    }

    const { data, error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });

    if (error) return c.json({ error: error.message }, 401);

    return c.json({ user: data.user, session: data.session });
  } catch (err) {
    return c.json({ error: err.message }, 500);
  }
});

router.post("/logout", async (c) => {
  try {
    const { error } = await supabase.auth.signOut();
    if (error) return c.json({ error: error.message }, 500);
    return c.json({ message: "Logged out successfully" });
  } catch (err) {
    return c.json({ error: err.message }, 500);
  }
});

export default router;
