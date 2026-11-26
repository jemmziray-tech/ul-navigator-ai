import { Suspense } from "react";
import type { Metadata } from "next";
import { ExamLookup } from "@/components/exam-lookup";

export const metadata: Metadata = { title: "Module exam lookup", description: "Check published UL module exam dates, times and venues, with the exam session and source-check timestamp." };
export default function Page() { return <Suspense fallback={<main className="p-10">Loading exam lookup…</main>}><ExamLookup /></Suspense>; }
