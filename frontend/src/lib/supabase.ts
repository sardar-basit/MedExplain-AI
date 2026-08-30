import { createClient } from "@supabase/supabase-js";

const supabaseUrl =
  process.env.NEXT_PUBLIC_SUPABASE_URL || "https://dokmqxuoqqsvelmrhxkj.supabase.co";
const supabaseAnonKey =
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ||
  "sb_publishable__F9Cer24mtjhS3gRLm1P-A_B33LIJWL";

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
