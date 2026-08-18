import { createClient } from "@supabase/supabase-js";
import { env } from "./env";

export const supabase = env.supabaseUrl
  ? createClient(env.supabaseUrl, env.supabaseAnonKey)
  : null;

export function getSupabase() {
  if (!supabase) {
    throw new Error(
      "Supabase is not configured. Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY in your environment."
    );
  }
  return supabase;
}
