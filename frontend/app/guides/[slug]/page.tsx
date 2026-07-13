import type { Metadata } from "next";
import { notFound } from "next/navigation";
import GuideArticle from "@/components/guides/GuideArticle";
import { getGuide, guideSlugs, relatedGuides } from "@/lib/guides";

// Pre-render every guide at build time (static, fast, SEO-friendly).
export function generateStaticParams() {
  return guideSlugs().map((slug) => ({ slug }));
}

export function generateMetadata({ params }: { params: { slug: string } }): Metadata {
  const guide = getGuide(params.slug);
  if (!guide) return { title: "Guide not found" };
  const title = `${guide.name} — Technique Guide`;
  return {
    title: guide.name,
    description: guide.summary,
    alternates: { canonical: `/guides/${guide.slug}` },
    openGraph: {
      title,
      description: guide.summary,
      type: "article",
      url: `/guides/${guide.slug}`,
    },
    twitter: { card: "summary_large_image", title, description: guide.summary },
    keywords: [
      guide.name,
      `${guide.name} technique`,
      `how to ${guide.name.toLowerCase()}`,
      ...guide.primaryMuscles,
      "form",
      "biomechanics",
    ],
  };
}

export default function GuidePage({ params }: { params: { slug: string } }) {
  const guide = getGuide(params.slug);
  if (!guide) notFound();

  const faqLd = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: guide.faqs.map((f) => ({
      "@type": "Question",
      name: f.q,
      acceptedAnswer: { "@type": "Answer", text: f.a },
    })),
  };

  return (
    <>
      <script
        type="application/ld+json"
        // eslint-disable-next-line react/no-danger
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqLd) }}
      />
      <GuideArticle guide={guide} related={relatedGuides(guide.related)} />
    </>
  );
}
