import type { NextConfig } from "next";

// Fully static: every artifact the app needs is baked in at build time from public/data.
const nextConfig: NextConfig = {
  output: "export",
  images: { unoptimized: true },
};

export default nextConfig;
