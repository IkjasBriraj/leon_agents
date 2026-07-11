"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import Cookies from "js-cookie";
import {
  LayoutDashboard,
  Bot,
  GitBranch,
  PlaySquare,
  LogOut,
  Cpu,
  Database,
  Wrench,
  Settings,
} from "lucide-react";
import { api, type User as UserType } from "@/lib/api";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<UserType | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = Cookies.get("agentcraft_token");
    if (!token) {
      router.push("/");
      return;
    }

    api.get<UserType>("/auth/me")
      .then((data) => {
        setUser(data);
        setLoading(false);
      })
      .catch(() => {
        Cookies.remove("agentcraft_token");
        router.push("/");
      });
  }, [router]);

  const handleLogout = () => {
    Cookies.remove("agentcraft_token");
    router.push("/");
  };

  if (loading) {
    return (
      <div
        style={{
          minHeight: "100vh",
          background: "var(--cds-background)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexDirection: "column",
          gap: 16,
        }}
      >
        <div
          style={{
            width: 40,
            height: 40,
            border: "3px solid rgba(69,137,255,0.2)",
            borderTop: "3px solid var(--cds-interactive)",
            borderRadius: "50%",
            animation: "spin 0.7s linear infinite",
          }}
        />
        <p style={{ fontSize: "0.875rem", color: "var(--cds-text-secondary)" }}>
          Initializing workspace…
        </p>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  const menuItems = [
    { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
    { name: "Agents", href: "/dashboard/agents", icon: Bot },
    { name: "Workflows", href: "/dashboard/workflows", icon: GitBranch },
    { name: "Execution Runs", href: "/dashboard/runs", icon: PlaySquare },
    { name: "Memory Explorer", href: "/dashboard/memory", icon: Database },
    { name: "Tools Registry", href: "/dashboard/tools", icon: Wrench },
    { name: "Settings", href: "/dashboard/settings", icon: Settings },
  ];

  return (
    <div className="app-layout">
      {/* ── Carbon Global Header ───────────────────────────────────────── */}
      <header className="app-topbar" style={{ justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {/* Brand mark */}
          <div
            style={{
              width: 32,
              height: 32,
              background: "rgba(15,98,254,0.12)",
              border: "1px solid rgba(69,137,255,0.25)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "var(--cds-link-primary)",
            }}
          >
            <Cpu className="w-4 h-4" />
          </div>
          <span
            style={{
              fontWeight: 600,
              fontSize: "0.875rem",
              letterSpacing: "0.01em",
              color: "var(--cds-text-primary)",
            }}
          >
            AgentCraft
          </span>
          <span
            style={{
              fontSize: "0.6875rem",
              fontWeight: 600,
              padding: "2px 8px",
              background: "rgba(15,98,254,0.10)",
              border: "1px solid rgba(69,137,255,0.20)",
              color: "var(--cds-link-primary)",
              letterSpacing: "0.04em",
            }}
          >
            v0.1
          </span>
        </div>

        {/* User area */}
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "6px 12px",
              background: "var(--cds-layer-02)",
              border: "1px solid var(--cds-border-subtle-00)",
            }}
          >
            {/* Avatar */}
            <div
              style={{
                width: 24,
                height: 24,
                background: "rgba(15,98,254,0.12)",
                border: "1px solid rgba(69,137,255,0.25)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "0.625rem",
                fontWeight: 700,
                color: "var(--cds-link-primary)",
                textTransform: "uppercase",
              }}
            >
              {user?.full_name?.charAt(0) || "U"}
            </div>
            <div>
              <p
                style={{
                  fontSize: "0.75rem",
                  fontWeight: 600,
                  color: "var(--cds-text-primary)",
                  lineHeight: 1.2,
                }}
              >
                {user?.full_name}
              </p>
              <p
                style={{
                  fontSize: "0.6875rem",
                  color: "var(--cds-text-helper)",
                  lineHeight: 1,
                  textTransform: "capitalize",
                }}
              >
                {user?.role}
              </p>
            </div>
          </div>

          <button
            onClick={handleLogout}
            className="btn btn-ghost btn-icon"
            title="Sign out"
            style={{ color: "var(--cds-text-secondary)" }}
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* ── Carbon SideNav ─────────────────────────────────────────────── */}
      <aside className="app-sidebar" style={{ display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
        <nav>
          {menuItems.map((item) => {
            const Icon = item.icon;
            const isActive =
              item.href === "/dashboard"
                ? pathname === "/dashboard"
                : pathname.startsWith(item.href);
            return (
              <Link
                key={item.name}
                href={item.href}
                className={`nav-item ${isActive ? "active" : ""}`}
              >
                <Icon />
                <span>{item.name}</span>
              </Link>
            );
          })}
        </nav>

        {/* Ollama connection pill */}
        <div
          style={{
            margin: "12px 16px",
            padding: "10px 12px",
            background: "var(--cds-layer-02)",
            border: "1px solid var(--cds-border-subtle-00)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                background: "var(--cds-support-success)",
                flexShrink: 0,
              }}
            />
            <span
              style={{
                fontSize: "0.625rem",
                fontWeight: 700,
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                color: "var(--cds-support-success)",
              }}
            >
              Ollama
            </span>
          </div>
          <p
            style={{
              fontSize: "0.6875rem",
              color: "var(--cds-text-secondary)",
              fontFamily: "'IBM Plex Mono', monospace",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            localhost:11434
          </p>
        </div>
      </aside>

      {/* ── Main Content ───────────────────────────────────────────────── */}
      <main className="app-main">{children}</main>
    </div>
  );
}
