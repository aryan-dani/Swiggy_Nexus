/** @type {import('next').NextConfig} */
const nextConfig = {
  // Dev HMR/fonts: browser may hit the UI as 127.0.0.1 while the server
  // bound hostname differs (or the reverse). Allow both loopback forms.
  allowedDevOrigins: ["127.0.0.1", "localhost"],
};

export default nextConfig;
