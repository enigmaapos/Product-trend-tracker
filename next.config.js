/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  images: {
    domains: [
      "p16-sign.tiktokcdn-us.com", // TikTok product thumbnails
      "p16.tiktokcdn.com",
      "lf16-tiktok-web.ttwstatic.com"
    ],
  },
  env: {
    API_BASE_URL: process.env.API_BASE_URL || "http://localhost:3000/api",
  },
};

module.exports = nextConfig;
