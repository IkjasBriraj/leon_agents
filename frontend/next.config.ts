import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  experimental: {
    // React 19 Server Actions
    serverActions: { bodySizeLimit: "4mb" },
  },
  // Allow images from common AI/avatar sources
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "avatars.githubusercontent.com" },
      { protocol: "https", hostname: "lh3.googleusercontent.com" },
    ],
  },
};

export default nextConfig;
