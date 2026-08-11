"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { Sidebar } from "@/components/sidebar";
import { Topbar } from "@/components/topbar";
import { UniversalCommandPalette } from "@/components/universal-command-palette";
import { ExperienceProvider } from "@/components/experience-provider";
import { ExperienceSettings } from "@/components/experience-settings";
import { KeyboardHelp } from "@/components/keyboard-help";

function ShellInner({ children }: { children: ReactNode }) {
  const pathname = usePathname() ?? "";
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  useEffect(() => { setMobileNavOpen(false); }, [pathname]);
  useEffect(() => {
    const handler = () => setMobileNavOpen((value) => !value);
    window.addEventListener("jl:toggle-nav", handler);
    return () => window.removeEventListener("jl:toggle-nav", handler);
  }, []);

  if (pathname === "/login") return <div className="auth-shell">{children}</div>;
  if (pathname.startsWith("/portal")) return <div className="portal-shell">{children}</div>;
  return (
    <div className="shell">
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <Sidebar mobileOpen={mobileNavOpen} onClose={() => setMobileNavOpen(false)} />
      <div className="content">
        <Topbar />
        <main id="main-content" tabIndex={-1}>{children}</main>
      </div>
      <UniversalCommandPalette />
      <ExperienceSettings />
      <KeyboardHelp />
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  return <ExperienceProvider><ShellInner>{children}</ShellInner></ExperienceProvider>;
}
