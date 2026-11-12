/** @type {import('next').NextConfig} */
const nextConfig = {
  // API base URL comes from the environment at build/run time.
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  },
};

module.exports = nextConfig;
