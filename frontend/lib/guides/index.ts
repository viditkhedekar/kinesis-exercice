// Guide registry. To add a new exercise guide, create one data file under
// ./data and register it here — the pages and components render it generically.
import type { GuideData } from "./types";
import benchPress from "./data/bench-press";
import bicepCurl from "./data/bicep-curl";
import deadlift from "./data/deadlift";
import lateralRaise from "./data/lateral-raise";
import squat from "./data/squat";

// Display order for the library index.
const GUIDES: GuideData[] = [squat, deadlift, benchPress, bicepCurl, lateralRaise];

const BY_SLUG: Record<string, GuideData> = Object.fromEntries(
  GUIDES.map((g) => [g.slug, g]),
);

export function allGuides(): GuideData[] {
  return GUIDES;
}

export function getGuide(slug: string): GuideData | undefined {
  return BY_SLUG[slug];
}

export function guideSlugs(): string[] {
  return GUIDES.map((g) => g.slug);
}

/** Resolve related-guide slugs to their data (skipping any that don't exist). */
export function relatedGuides(slugs: string[]): GuideData[] {
  return slugs.map((s) => BY_SLUG[s]).filter((g): g is GuideData => Boolean(g));
}

export type { GuideData };
