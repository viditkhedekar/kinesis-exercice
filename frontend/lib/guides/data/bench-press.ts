import type { GuideData } from "../types";

const guide: GuideData = {
  slug: "bench-press",
  name: "Bench Press",
  exerciseKey: "chest_press",
  category: "Upper body · Barbell",
  difficulty: "Intermediate",
  equipment: ["Barbell", "Bench", "Rack", "Weight plates"],
  primaryMuscles: ["Pectoralis major", "Anterior deltoid", "Triceps"],
  secondaryMuscles: ["Serratus anterior", "Upper back", "Forearms"],
  summary:
    "The benchmark upper-body press — a horizontal push that builds the chest, shoulders and triceps through a stable, retracted shoulder position.",
  intro:
    "The bench press trains the whole pushing chain from a supported position, letting you load the chest, front delts and triceps heavily. Its difficulty is deceptive: a good bench is as much about a stable base and bar path as it is about pressing strength.",
  demoCaption: "Side-on demonstration — touch the chest under control, press to a stacked lockout.",
  steps: [
    {
      phase: "Setup",
      body: "Lie back with eyes under the bar. Set your grip slightly wider than shoulder-width, pull your shoulder blades down and back, and plant your feet flat for a stable base.",
      cues: ["Eyes under the bar", "Shoulder blades retracted & depressed", "Feet planted, slight arch"],
    },
    {
      phase: "Starting Position",
      body: "Unrack to a position with the bar stacked over the shoulders and arms straight. Keep the upper back tight against the bench and maintain a natural arch through the lower back.",
      cues: ["Bar over shoulders at lockout", "Wrists stacked over elbows", "Upper back tight to the bench"],
    },
    {
      phase: "Execution",
      body: "Lower the bar to the lower chest / sternum with the elbows tucked to roughly 45–75° from the torso, then press up and slightly back so the bar finishes over the shoulders.",
      cues: ["Elbows ~45–75°, not flared", "Bar to the lower chest", "Press up and slightly back"],
    },
    {
      phase: "Top Position",
      body: "Finish with the elbows straight and the bar stacked over the shoulder joint — the position of least effort. Keep the shoulder blades retracted; don't let the shoulders roll forward off the bench.",
      cues: ["Elbows locked, bar over shoulders", "Shoulders stay back", "Ribs down, glutes on the bench"],
    },
    {
      phase: "Eccentric (lowering)",
      body: "Lower under control to a light touch on the chest — no bouncing. Keep tension in the upper back and maintain the bar path so the descent mirrors the press.",
      cues: ["Controlled descent", "Touch, don't bounce", "Keep the upper back tight"],
    },
    {
      phase: "Breathing",
      body: "Breathe in and brace at the top, hold through the descent and the press off the chest (the sticking point), then exhale near lockout. Keep the whole torso tight throughout.",
      cues: ["Inhale + brace at the top", "Hold off the chest", "Exhale near lockout"],
    },
    {
      phase: "Tempo",
      body: "A controlled 2–3 second descent to a defined touch point, then a strong press. Avoid heaving the bar off the chest — control on the way down is what makes the press consistent.",
      cues: ["~2–3s down", "Defined touch point", "Powerful, smooth press"],
    },
  ],
  biomechanics: [
    { title: "Retraction builds a stable shelf", body: "Pulling the shoulder blades down and back creates a stable platform and a healthier shoulder position, letting you press more with less strain on the joint." },
    { title: "The arch shortens the range", body: "A modest lower-back arch keeps the shoulders retracted and slightly reduces the distance the bar travels — this is a technique, not cheating, as long as the glutes stay on the bench." },
    { title: "Elbow angle protects the shoulder", body: "Flaring the elbows to 90° stresses the front of the shoulder; tucking to roughly 45–75° keeps the joint safer and puts the chest and triceps in a stronger line." },
    { title: "A diagonal bar path is efficient", body: "The bar touches the lower chest and finishes over the shoulders, so its path is a slight J. This keeps the load balanced over the shoulder joint at lockout." },
  ],
  mistakes: [
    {
      title: "Flaring the elbows to 90°",
      why: "Gripping too wide or pressing straight up with no tuck, often to feel more chest.",
      impact: "Places the shoulder in a vulnerable position and is a common cause of front-of-shoulder pain.",
      fix: "Tuck the elbows to 45–75° and lower to the lower chest rather than the collarbone.",
    },
    {
      title: "Bouncing the bar off the chest",
      why: "Using momentum to get past the hardest part of the press.",
      impact: "Removes the value of the bottom range and risks rib and sternum strain under heavy load.",
      fix: "Lower under control to a light, paused touch and press from a dead position.",
    },
    {
      title: "Losing shoulder-blade retraction",
      why: "Not setting the back before unracking, or letting the shoulders roll forward at lockout.",
      impact: "Removes the stable shelf, reduces power, and exposes the shoulder joint to strain.",
      fix: "Set and hold retraction from unrack to rack; think 'proud chest, shoulders in your back pockets'.",
    },
    {
      title: "Lifting the hips off the bench",
      why: "Trying to press more weight than the upper body can move on its own.",
      impact: "Turns the lift into a decline press and greatly increases lower-back stress.",
      fix: "Keep the glutes on the bench and reduce the load; drive the feet into the floor without lifting the hips.",
    },
    {
      title: "Uneven press (one side leads)",
      why: "A strength imbalance or an off-centre grip and bar.",
      impact: "Overloads the stronger side, limits the weaker side, and can nag the shoulder over time.",
      fix: "Centre the bar with even grip marks, and add dumbbell pressing to build balanced strength.",
    },
    {
      title: "Bar drifting toward the face",
      why: "Weak triceps at lockout or pressing straight up from a high touch point.",
      impact: "Moves the load behind the shoulders where it's hardest to control and stalls the lockout.",
      fix: "Touch lower on the chest and press up and slightly back so the bar finishes over the shoulders.",
    },
    {
      title: "Wrists bent back under the bar",
      why: "Letting the bar sit high in the palm rather than over the forearm.",
      impact: "Strains the wrist and leaks force before it reaches the bar.",
      fix: "Grip so the bar sits low in the palm over a straight wrist, stacked directly over the elbow.",
    },
  ],
  aiFocus: [
    { label: "Bar path", detail: "Estimates the touch point and the diagonal path to lockout to check the bar stays balanced over the shoulders." },
    { label: "Elbow angle", detail: "Measures how far the elbows flare from the torso to flag a shoulder-risky press." },
    { label: "Left/right symmetry", detail: "Compares the two arms through the press to catch one side leading or lagging." },
    { label: "Range of motion", detail: "Confirms a full chest touch and a complete lockout on each rep." },
    { label: "Tempo & control", detail: "Times the descent and detects bouncing off the chest versus a controlled touch." },
    { label: "Stability", detail: "Watches for hip lift and a wandering bar as signs the load is too heavy to control." },
  ],
  coaching: [
    {
      level: "Beginner",
      tips: [
        "Learn to set the shoulder blades and hold the arch before adding weight.",
        "Always bench with safeties or a spotter so you can fail safely.",
        "Start with dumbbells to build a balanced, pain-free press.",
      ],
    },
    {
      level: "Intermediate",
      tips: [
        "Add paused bench (1–2s on the chest) to build strength off the bottom.",
        "Use a consistent grip width and touch point so every rep is comparable.",
        "Balance pressing with plenty of upper-back rowing for shoulder health.",
      ],
    },
    {
      level: "Advanced",
      tips: [
        "Attack sticking points with board presses, spoto presses or tempo work.",
        "Cycle intensity and volume in blocks, keeping technique crisp on top sets.",
        "Autoregulate with RPE and keep 1–2 reps in reserve on most working sets.",
      ],
    },
  ],
  safety: [
    "Never bench heavy without safety arms or a competent spotter.",
    "Don't use collars if you train alone without safeties — so you can tip a failed bar off to the side.",
    "Keep the glutes on the bench and avoid excessive arching if it bothers your back.",
    "Warm up the shoulders and ramp the load; stop if you feel joint (not muscle) pain.",
    "Rack the bar fully before relaxing — many injuries happen on a rushed re-rack.",
  ],
  faqs: [
    { q: "Where should the bar touch?", a: "Around the lower chest or sternum, with the elbows tucked. Touching too high near the collarbone flares the elbows and stresses the shoulder." },
    { q: "Is arching my back cheating?", a: "A moderate arch that keeps your shoulders retracted and glutes on the bench is standard technique. Excessive arching purely to shorten the range is a different matter — keep it comfortable." },
    { q: "How wide should my grip be?", a: "Slightly wider than shoulder-width for most people, so the forearms are roughly vertical at the bottom. Very wide grips stress the shoulders; very narrow shifts work to the triceps." },
    { q: "Why does one arm press faster?", a: "Usually a strength imbalance or an off-centre setup. Centre the bar and add unilateral dumbbell work to even it out." },
    { q: "Should I bench to a full lockout?", a: "Yes — finish with straight elbows and the bar stacked over the shoulders, keeping the shoulder blades retracted rather than rolling the shoulders forward." },
  ],
  related: ["dumbbell-bicep-curl", "dumbbell-lateral-raise"],
};

export default guide;
