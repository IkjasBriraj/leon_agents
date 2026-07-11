import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "AgentCraft", template: "%s | AgentCraft" },
  description: "Enterprise-grade agentic AI platform — build, debug, and deploy intelligent agent workflows",
  keywords: ["AI agents", "LLM", "workflow automation", "agentic AI", "Ollama"],
  authors: [{ name: "AgentCraft" }],
  openGraph: {
    title: "AgentCraft",
    description: "Enterprise-grade agentic AI platform",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="icon" href="/favicon.ico" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </head>
      <body>{children}</body>
    </html>
  );
}
