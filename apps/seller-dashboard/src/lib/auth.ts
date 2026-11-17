import { createClient, type SupabaseClient } from "@supabase/supabase-js";
let client: SupabaseClient | undefined;
const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

export function passwordLoginId(identifier: string) {
  const value = identifier.trim();
  // Existing sellers keep their original Supabase identity.
  return value.includes("@")
    ? value
    : value.toLowerCase() + "@usernames.rescueloop.invalid";
}

export function supabase() {
  if (!url || !key)
    throw new Error(
      "Supabase sign-in is not configured. Set the public URL and anonymous key.",
    );
  return (client ??= createClient(url, key));
}
