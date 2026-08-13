import type { MetadataRoute } from "next";
import { TOOL_CATALOG } from "@/lib/tools";

/**
 * Only genuinely public pages belong here. Everything behind the session
 * cookie (matters, clients, evidence, billing) is deliberately absent — a
 * sitemap entry that returns a login redirect is worse than no entry.
 */
const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://juniorlawyer.app";

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();
  return [
    { url: SITE_URL, lastModified: now, changeFrequency: "weekly", priority: 1 },
    { url: `${SITE_URL}/tools`, lastModified: now, changeFrequency: "weekly", priority: 0.9 },
    ...TOOL_CATALOG.map((tool) => ({
      url: `${SITE_URL}${tool.href}`,
      lastModified: now,
      changeFrequency: "monthly" as const,
      priority: 0.8,
    })),
  ];
}
