// Structured content model for an exercise guide. Guides are pure data — the
// React components render any guide generically, so adding a new exercise means
// adding one more data file (see lib/guides/index.ts) and nothing else.

export type Difficulty = "Beginner" | "Intermediate" | "Advanced";

/** One phase of the step-by-step walkthrough (fixed, ordered set of phases). */
export interface GuideStep {
  /** Phase label, e.g. "Setup", "Execution". */
  phase: string;
  body: string;
  /** Optional short cues shown as a checklist. */
  cues?: string[];
}

export interface Biomechanic {
  title: string;
  body: string;
}

export interface Mistake {
  title: string;
  why: string; // why it happens
  impact: string; // how it affects performance / injury risk
  fix: string; // exactly how to fix it
}

/** What the Physiqal AI inspects for this movement. */
export interface AiFocus {
  label: string; // e.g. "Range of motion"
  detail: string;
}

export interface CoachingTier {
  level: Difficulty;
  tips: string[];
}

export interface Faq {
  q: string;
  a: string;
}

export interface GuideData {
  slug: string;
  name: string;
  /** Analysis exercise key, when Physiqal can analyse this lift (links to /upload). */
  exerciseKey?: string;
  /** Short categoriser, e.g. "Lower body · Barbell". */
  category: string;
  difficulty: Difficulty;
  equipment: string[];
  primaryMuscles: string[];
  secondaryMuscles: string[];
  /** One-line summary used on cards and as the meta description. */
  summary: string;
  /** 1–2 sentence professional introduction shown in the hero. */
  intro: string;
  /** Caption for the animated-demonstration placeholder. */
  demoCaption: string;
  steps: GuideStep[];
  biomechanics: Biomechanic[];
  mistakes: Mistake[]; // 5–8
  aiFocus: AiFocus[];
  coaching: CoachingTier[];
  safety: string[];
  faqs: Faq[];
  /** Slugs of related guides. */
  related: string[];
}
