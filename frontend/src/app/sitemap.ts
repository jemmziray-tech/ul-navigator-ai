import type { MetadataRoute } from "next";

export default function sitemap(): MetadataRoute.Sitemap {
  return ["", "/courses", "/curricula", "/explorer", "/tools", "/grade-planner", "/knowledge-health", "/about", "/privacy"].map(path => ({
    url: `https://ul-navigator-ai.vercel.app${path}`,
  }));
}
