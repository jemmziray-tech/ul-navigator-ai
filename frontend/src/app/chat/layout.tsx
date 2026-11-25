import type { Metadata } from "next";

export const metadata: Metadata = { title: "Ask AI", robots: { index: false, follow: false } };

export default function ChatLayout({ children }: { children: React.ReactNode }) { return children; }
