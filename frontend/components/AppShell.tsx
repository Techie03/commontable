// Shared shell for every MVP slice page: auth provider, role aware header,
// and a centered main column. The root layout is owned by the landing page,
// so each slice page renders inside this shell instead.

"use client";

import type { ReactNode } from "react";
import { AuthProvider } from "@/lib/auth";
import SiteFooter from "./SiteFooter";
import SiteHeader from "./SiteHeader";

export default function AppShell({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <SiteHeader />
      <main className="app-main">
        <div className="container">{children}</div>
      </main>
      <SiteFooter />
    </AuthProvider>
  );
}
