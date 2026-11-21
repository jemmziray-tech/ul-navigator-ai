import type { Metadata } from "next";
import { GradePlanner } from "@/components/grade-planner";

export const metadata: Metadata = {
  title: "Grade Target Planner",
  description: "Explore the grades needed to reach a QCA target using UL's 2026/27 quality point values.",
};

export default function Page() { return <GradePlanner />; }
