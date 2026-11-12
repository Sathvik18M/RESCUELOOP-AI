import type { NextConfig } from "next";
import { loadEnvConfig } from "@next/env";
import { resolve } from "node:path";
// Next loads the app directory first; reload so the repository-root .env is included.
loadEnvConfig(
  resolve(process.cwd(), "../.."),
  process.env.NODE_ENV !== "production",
  console,
  true,
);
const nextConfig: NextConfig = {
  distDir: process.env.NEXT_DIST_DIR || ".next-rebuild",
  poweredByHeader: false,
  devIndicators: false,
  async rewrites() {
    if (
      process.env.NODE_ENV !== "development" ||
      process.env.LOCAL_API_PROXY !== "true"
    ) {
      return [];
    }
    // Local presentation UI, with the same authenticated hosted seller API.
    // Fixed destinations preserve authentication and avoid browser CORS errors.
    return [
      {
        source: "/backend/api/:path*",
        destination: "https://rescueloop-api.onrender.com/api/:path*",
      },
      {
        source: "/backend/health",
        destination: "https://rescueloop-api.onrender.com/health",
      },
    ];
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
        ],
      },
    ];
  },
};
export default nextConfig;
