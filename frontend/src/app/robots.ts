import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: "/", disallow: ["/admin", "/chat", "/backend/"] },
    sitemap: "https://ul-navigator-ai.vercel.app/sitemap.xml",
  };
}
