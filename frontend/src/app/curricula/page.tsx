import { Suspense } from "react";
import type { Metadata } from "next";
import { CurriculumExplorer } from "@/components/curriculum-explorer";

export const metadata: Metadata = { title: "Programme modules by semester", description: "Explore official UL programme module lists by year, semester and pathway, with linked module descriptors." };
export default function Page() { return <Suspense fallback={<main className="p-10">Loading programme modules…</main>}><CurriculumExplorer /></Suspense>; }
