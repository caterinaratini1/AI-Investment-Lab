import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";

const siteUrl = process.env.AIL_WEB_SITE_URL ?? "http://localhost:3000";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: "AI Investment Lab — an auditable AI portfolio experiment",
  description:
    "Can an AI portfolio manager beat the market? Follow every fictional trade, daily valuation, and benchmark comparison.",
  openGraph: {
    title: "AI Investment Lab",
    description: "AI portfolio vs the world — recorded, reproducible, open.",
    type: "website",
    images: [{ url: "/og.png", width: 1200, height: 630, alt: "AI Investment Lab portfolio and benchmark lines" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "AI Investment Lab",
    description: "AI portfolio vs the world — recorded, reproducible, open.",
    images: ["/og.png"],
  },
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
