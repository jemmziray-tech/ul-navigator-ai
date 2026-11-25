import Link from "next/link";
import type { Metadata } from "next";
import { SiteFooter, SiteHeader } from "@/components/site";
import { Card } from "@/components/ui";

export const metadata: Metadata = { title: "Privacy and your data" };

export default function Privacy() {
  return <><SiteHeader /><main id="main" className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
    <p className="text-xs font-semibold uppercase tracking-widest text-emerald">Updated 25 November 2026</p>
    <h1 className="mt-3 font-display text-4xl">Your data, explained simply.</h1>
    <p className="mt-5 text-lg leading-relaxed text-muted">You can use UL Navigator AI without an account. Please keep student numbers, PPS numbers, passwords, financial details and other sensitive information out of your questions.</p>
    <div className="mt-8 space-y-5">
      <Card className="p-6"><h2 className="text-lg font-semibold">Conversations and feedback</h2><p className="mt-3 leading-relaxed text-muted">A random identifier is saved in your browser so the service can show your conversation history. Questions, answers, citations and feedback may be stored on the service. Anyone with access to the same browser can potentially view that history. If browser storage is blocked, a separate temporary identity is used for that session; history may not be available after a reload.</p><p className="mt-3 leading-relaxed text-muted">Use the delete button beside a conversation to remove it from live chat history. Operational records, including questions logged for answer quality, and backup copies can remain until routine expiry. Old records are periodically removed under the service’s retention setting.</p></Card>
      <Card className="p-6"><h2 className="text-lg font-semibold">What is sent to the AI provider</h2><p className="mt-3 leading-relaxed text-muted">When an AI answer is requested, your question, recent conversation context and relevant public source passages may be sent to Google’s Gemini API. The service runs on Google Cloud and the website is hosted on Vercel. Those providers also process the connection and operational information needed to deliver the service.</p><a href="https://ai.google.dev/gemini-api/terms" target="_blank" rel="noreferrer" className="mt-3 inline-block text-emerald underline underline-offset-4">Google Gemini API terms</a></Card>
      <Card className="p-6"><h2 className="text-lg font-semibold">Grades and course shortlists</h2><p className="mt-3 leading-relaxed text-muted">The Grade Target Planner calculates in your browser. Its grade inputs are not sent to the AI or stored by the planner. Course shortlists are saved in your browser. A shared course comparison link contains the selected public course identifiers.</p><Link href="/grade-planner" className="mt-3 inline-block text-emerald underline underline-offset-4">Open the Grade Target Planner</Link></Card>
      <Card className="p-6"><h2 className="text-lg font-semibold">An independent service</h2><p className="mt-3 leading-relaxed text-muted">UL Navigator AI is an independently maintained information service. It cannot access your UL student account, academic record or private university systems. Public source collection is separate from the questions people ask.</p><Link href="/about" className="mt-3 inline-block text-emerald underline underline-offset-4">About the service</Link></Card>
    </div>
  </main><SiteFooter /></>;
}
