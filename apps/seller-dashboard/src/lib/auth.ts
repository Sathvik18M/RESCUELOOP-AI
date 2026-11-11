import { createClient } from "@supabase/supabase-js";
export function supabase() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key)
    throw new Error(
      "Supabase sign-in is not configured. Set the public URL and anonymous key.",
    );
  return createClient(url, key);
}
