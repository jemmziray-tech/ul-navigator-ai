import type { Metadata } from "next";
import catalogue from "@/data/courses.json";
import { CourseFinder } from "@/components/course-finder";

export const metadata: Metadata = {
  title: "Course finder",
  description: "Explore and compare University of Limerick programmes, save your shortlist and check the official sources behind each detail.",
};

export default function CoursesPage() {
  return <CourseFinder courses={catalogue.courses} generatedAt={catalogue.generatedAt} />;
}
