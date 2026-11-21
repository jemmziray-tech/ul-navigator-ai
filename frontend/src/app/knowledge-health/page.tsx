import type { Metadata } from "next";
import catalogue from "@/data/courses.json";
import { KnowledgeHealth } from "@/components/knowledge-health";

export const metadata: Metadata = {
  title: "Knowledge health",
  description: "Inspect UL Navigator’s source coverage, collection snapshot and course information gaps.",
};

export default function KnowledgeHealthPage() {
  return <KnowledgeHealth generatedAt={catalogue.generatedAt} coverage={catalogue.coverage}
    collection={{ at: catalogue.collectionSnapshot.updated_at, discovered: catalogue.collectionSnapshot.queued_urls,
      collected: catalogue.collectionSnapshot.collected_documents ?? catalogue.collectionSnapshot.counts.ready ?? 0 }} />;
}
