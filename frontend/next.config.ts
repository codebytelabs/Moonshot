import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactCompiler: true,
  async rewrites() {
    return [
      {
        source: "/office/:path*",
        destination: "http://localhost:4001/office/:path*",
      },
    ];
  },
};

export default nextConfig;
