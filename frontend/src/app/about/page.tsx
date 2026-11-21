import Link from "next/link";
import type { Metadata } from "next";
import { SiteFooter, SiteHeader, UniversityResourceMark } from "@/components/site";
import { Card } from "@/components/ui";

export const metadata: Metadata = { title: "About" };

export default function About() {
  return <><SiteHeader /><main id="main" className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
    <UniversityResourceMark />
    <p className="mt-8 text-xs font-semibold uppercase tracking-widest text-emerald">Public beta · Built by a UL student</p>
    <h1 className="mt-3 font-display text-4xl">A clearer next step at UL.</h1>
    <p className="mt-5 text-lg leading-relaxed text-muted">UL Navigator AI brings course exploration, grade planning and questions about student life into one place. It is an independent student project created by John Elifuraha Mziray, studying BSc Artificial Intelligence &amp; Machine Learning at the University of Limerick.</p>
    <div className="mt-8 space-y-5">
      <Card className="p-6"><h2 className="text-lg font-semibold">How to use it well</h2><p className="mt-3 leading-relaxed text-muted">Ask a question in your own words. Include your programme and academic year when they matter. Follow the citations to check the source, and confirm decisions about fees, immigration, eligibility and progression with the relevant UL office.</p><p className="mt-3 text-muted">If a response is unclear or unhelpful, use its thumbs-down button. This records feedback for the project maintainer.</p></Card>
      <Card className="p-6"><h2 className="text-lg font-semibold">Clear about its limits</h2><p className="mt-3 leading-relaxed text-muted">The knowledge collection is still growing. It does not contain every UL page or programme detail. Answers can be incomplete or wrong, and course information may change after it was collected. The grade planner gives an estimate for the credits you enter; programme rules can affect an official result.</p><Link href="/knowledge-health" className="mt-3 inline-block text-emerald underline underline-offset-4">Check source coverage and gaps</Link></Card>
      <Card className="p-6"><h2 className="text-lg font-semibold">Independent identity</h2><p className="mt-3 leading-relaxed text-muted">UL Navigator AI is not an official University of Limerick service and is not presented as endorsed by the university. The university logo identifies the official institution whose public resources are referenced. The compass mark identifies this independent project.</p><a href="https://www.ul.ie/" target="_blank" rel="noreferrer" className="mt-3 inline-block text-emerald underline underline-offset-4">Visit the official University of Limerick website</a></Card>
    </div>
    <div className="mt-8 flex flex-wrap gap-5 text-sm"><Link href="/chat" className="text-emerald underline underline-offset-4">Ask a question</Link><Link href="/courses" className="text-emerald underline underline-offset-4">Find a course</Link><Link href="/grade-planner" className="text-emerald underline underline-offset-4">Plan your grades</Link><Link href="/privacy" className="text-emerald underline underline-offset-4">Read the privacy information</Link></div>
  </main><SiteFooter /></>;
}
