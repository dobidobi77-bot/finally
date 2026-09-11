import type { NextConfig } from "next";

/**
 * Static export: `next build` writes a fully static site to `out/`,
 * which the FastAPI container serves from `static/`. No server runtime.
 */
const nextConfig: NextConfig = {
  output: "export",
  images: { unoptimized: true },
  trailingSlash: true,
  reactStrictMode: true,
};

export default nextConfig;
