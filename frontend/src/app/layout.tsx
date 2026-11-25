import type { Metadata, Viewport } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import "@fontsource-variable/fraunces";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: { default: "UL Navigator AI", template: "%s · UL Navigator AI" },
  description:
    "Explore University of Limerick courses, semester modules and student services with an independent AI assistant grounded in official sources.",
  metadataBase: new URL("https://ul-navigator-ai.vercel.app"),
  applicationName: "UL Navigator AI",
  openGraph: { type: "website", siteName: "UL Navigator AI", title: "UL Navigator AI", description: "Courses, modules and answers grounded in official UL sources." },
  twitter: { card: "summary", title: "UL Navigator AI", description: "Courses, modules and answers grounded in official UL sources." },
  robots: { index: true, follow: true },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f8f7f2" },
    { media: "(prefers-color-scheme: dark)", color: "#0f1412" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-IE" suppressHydrationWarning className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body className="min-h-dvh">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
