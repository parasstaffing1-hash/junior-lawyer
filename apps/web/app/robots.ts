import type { MetadataRoute } from "next";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://juniorlawyer.app";

/**
 * The tools are the public surface. Every workspace route holds client matter
 * data and is disallowed explicitly — crawlers would only reach a login page,
 * and the path names themselves leak nothing useful.
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: ["/", "/tools"],
        disallow: [
          "/api/",
          "/backend/",
          "/assistant",
          "/chat",
          "/matters",
          "/clients",
          "/cases",
          "/evidence",
          "/documents",
          "/billing",
          "/finance",
          "/portal",
          "/security",
          "/collaboration",
          "/operations",
          "/system-health",
          "/deployment",
          "/release",
          "/qa",
          "/validation",
          "/legal-data",
          "/knowledge",
          "/analytics",
          "/integrations",
          "/onboarding",
          "/login",
        ],
      },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
