import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import { AppShell } from "@/components/app-shell";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://juniorlawyer.app";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  // Per-page titles read as "Court fee — free legal tool · Junior Lawyer".
  title: {
    default: "Junior Lawyer — bilingual legal workspace",
    template: "%s · Junior Lawyer",
  },
  description: "Bilingual deterministic-first legal workspace",
  openGraph: {
    siteName: "Junior Lawyer",
    type: "website",
    locale: "en_IN",
  },
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
