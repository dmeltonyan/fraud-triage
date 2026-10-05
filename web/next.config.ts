import type { NextConfig } from "next";
import { PHASE_PRODUCTION_BUILD } from "next/constants";

// NEXT_PUBLIC_API_URL is written into the site when it's built. If it's missing on
// a host like Vercel, the site would deploy "successfully" and then fail for every
// visitor, so a production build stops here with a clear message instead.
// (`npm run dev` keeps its local default; see web/lib/api.ts.)
function checkApiUrl() {
  const url = process.env.NEXT_PUBLIC_API_URL;
  if (!url) {
    throw new Error(
      "NEXT_PUBLIC_API_URL is not set. Set it to the API's address (for example https://your-api.onrender.com) " +
        "in Vercel's environment variables, or in web/.env.local for a local build.",
    );
  }
  if (process.env.VERCEL && /localhost|127\.0\.0\.1/.test(url)) {
    throw new Error(`NEXT_PUBLIC_API_URL is ${url}, a local address, which visitors can't reach. Use the Render address.`);
  }
}

export default function config(phase: string): NextConfig {
  if (phase === PHASE_PRODUCTION_BUILD) checkApiUrl();
  return {};
}
