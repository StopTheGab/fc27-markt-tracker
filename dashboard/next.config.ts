import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  images: { unoptimized: true },
  poweredByHeader: false,
  // next dev soll keine AGENTS.md/CLAUDE.md in den Projektordner schreiben
  agentRules: false,
};

export default nextConfig;
