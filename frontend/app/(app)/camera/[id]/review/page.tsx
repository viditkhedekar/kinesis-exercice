"use client";

import { useParams } from "next/navigation";
import LiveReview from "@/components/live/LiveReview";

export default function LiveReviewPage() {
  const params = useParams();
  return <LiveReview sessionId={Number(params.id)} />;
}
