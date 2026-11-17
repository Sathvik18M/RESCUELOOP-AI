import { createClient, type SupabaseClient } from "@supabase/supabase-js";
let client: SupabaseClient | undefined;
const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

export async function googleSignInEnabled(
  signal: AbortSignal,
): Promise<boolean> {
  if (!url || !key) return false;
  const response = await fetch(new URL("/auth/v1/settings", url), {
    headers: { apikey: key },
    signal,
  });
  return response.ok && (await response.json()).external?.google === true;
}

export function supabase() {
  if (!url || !key)
    throw new Error(
      "Supabase sign-in is not configured. Set the public URL and anonymous key.",
    );
  return (client ??= createClient(url, key));
}
