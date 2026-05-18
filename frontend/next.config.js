/** @type {import('next').NextConfig} */
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const OIDC_ISSUER = process.env.NEXT_PUBLIC_OIDC_ISSUER || "http://localhost:8080";

// connect-src must include the API origin (XHR/SSE) and the OIDC issuer
// (OIDC discovery/redirects from the browser). "self" covers same-origin
// fetches when the frontend is fronted by nginx.
const connectSrc = ["'self'", API_URL, OIDC_ISSUER]
  .filter(Boolean)
  .join(" ");

const nextConfig = {
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          {
            key: "Content-Security-Policy",
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-eval' 'unsafe-inline'",
              "style-src 'self' 'unsafe-inline'",
              "img-src 'self' data: blob: https://cdn.jsdelivr.net",
              `connect-src ${connectSrc}`,
              "font-src 'self' data:",
              "frame-ancestors 'none'",
            ].join("; "),
          },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
  transpilePackages: ["antd"],
  output: "standalone",
};

module.exports = nextConfig;
