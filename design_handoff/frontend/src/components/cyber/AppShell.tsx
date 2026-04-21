"use client";

import type { ReactNode } from "react";
import { usePathname } from "next/navigation";
import { Sidebar } from "@/components/layout/Sidebar";
import { StatusBar } from "./StatusBar";

interface Props {
  children: ReactNode;
}

export function AppShell({ children }: Props) {
  const pathname = usePathname() || "/";

  const view = pathname.startsWith("/chat")
    ? "dialogue"
    : pathname.startsWith("/graph")
    ? "knowledge-map"
    : pathname.startsWith("/tasks")
    ? "task-bank"
    : pathname.startsWith("/sources")
    ? "sources"
    : pathname.startsWith("/profile")
    ? "profile"
    : pathname.startsWith("/settings")
    ? "settings"
    : "home";

  return (
    <>
      <StatusBar view={view} />
      <div className="flex flex-1 min-h-0">
        <Sidebar />
        <main
          className="flex-1 flex flex-col relative"
          style={{ minWidth: 0, minHeight: 0, overflow: "hidden" }}
        >
          {children}
        </main>
      </div>
    </>
  );
}
