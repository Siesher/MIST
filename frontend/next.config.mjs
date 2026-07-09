/** @type {import('next').NextConfig} */
const nextConfig = {
  // standalone: Dockerfile-стадия serve копирует .next/standalone —
  // без этого прод-образ получает пустой сервер
  output: "standalone",
};

export default nextConfig;
