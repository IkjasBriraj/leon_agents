"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Cookies from "js-cookie";
import { Cpu, Lock, Mail, User, Shield } from "lucide-react";
import { api } from "@/lib/api";

export default function AuthPage() {
  const router = useRouter();
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [orgName, setOrgName] = useState("");
  const [orgSlug, setOrgSlug] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = Cookies.get("agentcraft_token");
    if (token) {
      router.push("/dashboard");
    }
  }, [router]);

  const handleOrgNameChange = (val: string) => {
    setOrgName(val);
    setOrgSlug(val.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, ""));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      if (isLogin) {
        const res = await api.post<{ access_token: string }>("/auth/login", {
          email,
          password,
        });
        Cookies.set("agentcraft_token", res.access_token, { expires: 1 });
        router.push("/dashboard");
      } else {
        const res = await api.post<{ access_token: string }>("/auth/register", {
          email,
          password,
          full_name: fullName,
          org_name: orgName,
          org_slug: orgSlug,
        });
        Cookies.set("agentcraft_token", res.access_token, { expires: 1 });
        router.push("/dashboard");
      }
    } catch (err: any) {
      setError(err.message || "Authentication failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main
      className="min-h-screen flex items-center justify-center p-4"
      style={{ background: "var(--cds-background)" }}
    >
      {/* Carbon login panel — max-width 400px, centered */}
      <div
        className="w-full animate-fade-in"
        style={{ maxWidth: 400 }}
      >
        {/* Brand header */}
        <div className="flex flex-col items-center mb-8 gap-3">
          <div
            className="flex items-center justify-center"
            style={{
              width: 48,
              height: 48,
              background: "rgba(15,98,254,0.10)",
              border: "1px solid rgba(69,137,255,0.25)",
              color: "var(--cds-link-primary)",
            }}
          >
            <Cpu className="w-6 h-6" />
          </div>
          <div className="text-center">
            <h1 style={{ fontSize: "1.25rem", fontWeight: 400, color: "var(--cds-text-primary)" }}>
              AgentCraft
            </h1>
            <p style={{ fontSize: "0.875rem", color: "var(--cds-text-secondary)", marginTop: 4 }}>
              {isLogin
                ? "Sign in to manage your agentic workflows"
                : "Register to create an isolated workspace"}
            </p>
          </div>
        </div>

        {/* Card */}
        <div
          style={{
            background: "var(--cds-layer-01)",
            border: "1px solid var(--cds-border-subtle-00)",
          }}
        >
          {/* Dividing header bar */}
          <div
            style={{
              padding: "12px 16px",
              borderBottom: "1px solid var(--cds-border-subtle-00)",
              background: "var(--cds-layer-02)",
            }}
          >
            <span
              style={{
                fontSize: "0.75rem",
                fontWeight: 600,
                color: "var(--cds-text-secondary)",
                letterSpacing: "0.02em",
                textTransform: "uppercase",
              }}
            >
              {isLogin ? "Sign In" : "Create Account"}
            </span>
          </div>

          <div style={{ padding: "var(--spacing-06)" }}>
            {error && (
              <div className="cds-notification error mb-5">
                <span>{error}</span>
              </div>
            )}

            <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              {!isLogin && (
                <>
                  <div>
                    <label className="input-label">Full Name</label>
                    <div style={{ position: "relative" }}>
                      <User
                        className="w-4 h-4"
                        style={{
                          position: "absolute",
                          left: 12,
                          top: "50%",
                          transform: "translateY(-50%)",
                          color: "var(--cds-text-placeholder)",
                        }}
                      />
                      <input
                        type="text"
                        required
                        className="input"
                        style={{ paddingLeft: 36 }}
                        placeholder="Jane Doe"
                        value={fullName}
                        onChange={(e) => setFullName(e.target.value)}
                      />
                    </div>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                    <div>
                      <label className="input-label">Org Name</label>
                      <div style={{ position: "relative" }}>
                        <Shield
                          className="w-4 h-4"
                          style={{
                            position: "absolute",
                            left: 12,
                            top: "50%",
                            transform: "translateY(-50%)",
                            color: "var(--cds-text-placeholder)",
                          }}
                        />
                        <input
                          type="text"
                          required
                          className="input"
                          style={{ paddingLeft: 36 }}
                          placeholder="My Team"
                          value={orgName}
                          onChange={(e) => handleOrgNameChange(e.target.value)}
                        />
                      </div>
                    </div>
                    <div>
                      <label className="input-label">Org Slug</label>
                      <input
                        type="text"
                        required
                        disabled
                        className="input"
                        placeholder="my-team"
                        value={orgSlug}
                        style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.75rem" }}
                      />
                    </div>
                  </div>
                </>
              )}

              <div>
                <label className="input-label">Email Address</label>
                <div style={{ position: "relative" }}>
                  <Mail
                    className="w-4 h-4"
                    style={{
                      position: "absolute",
                      left: 12,
                      top: "50%",
                      transform: "translateY(-50%)",
                      color: "var(--cds-text-placeholder)",
                    }}
                  />
                  <input
                    type="email"
                    required
                    className="input"
                    style={{ paddingLeft: 36 }}
                    placeholder="you@domain.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                </div>
              </div>

              <div>
                <label className="input-label">Password</label>
                <div style={{ position: "relative" }}>
                  <Lock
                    className="w-4 h-4"
                    style={{
                      position: "absolute",
                      left: 12,
                      top: "50%",
                      transform: "translateY(-50%)",
                      color: "var(--cds-text-placeholder)",
                    }}
                  />
                  <input
                    type="password"
                    required
                    className="input"
                    style={{ paddingLeft: 36 }}
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="btn btn-primary"
                style={{ width: "100%", marginTop: 4, minHeight: 48, fontSize: "0.875rem" }}
              >
                {loading ? (
                  <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span
                      style={{
                        width: 16,
                        height: 16,
                        border: "2px solid rgba(255,255,255,0.25)",
                        borderTop: "2px solid #fff",
                        borderRadius: "50%",
                        animation: "spin 0.6s linear infinite",
                        display: "inline-block",
                      }}
                    />
                    Processing...
                  </span>
                ) : isLogin ? (
                  "Sign In"
                ) : (
                  "Create Organization"
                )}
              </button>
            </form>
          </div>

          <div
            style={{
              padding: "12px 24px",
              borderTop: "1px solid var(--cds-border-subtle-00)",
              textAlign: "center",
            }}
          >
            <button
              onClick={() => setIsLogin(!isLogin)}
              style={{
                background: "none",
                border: "none",
                cursor: "pointer",
                fontSize: "0.875rem",
                color: "var(--cds-link-primary)",
                transition: "color 110ms",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.color = "var(--cds-link-primary-hover)")}
              onMouseLeave={(e) => (e.currentTarget.style.color = "var(--cds-link-primary)")}
            >
              {isLogin ? "New workspace? Register here" : "Already have an account? Sign in"}
            </button>
          </div>
        </div>
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </main>
  );
}
