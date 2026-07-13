import type { GuideData } from "../types";

const guide: GuideData = {
  slug: "barbell-back-squat",
  name: "Barbell Back Squat",
  exerciseKey: "squat",
  category: "Lower body · Barbell",
  difficulty: "Intermediate",
  equipment: ["Barbell", "Squat rack", "Weight plates"],
  primaryMuscles: ["Quadriceps", "Gluteus maximus", "Adductors"],
  secondaryMuscles: ["Hamstrings", "Erector spinae", "Core"],
  summary:
    "The foundational lower-body strength lift — a loaded knee-and-hip flexion pattern that builds the quads, glutes and trunk together.",
  intro:
    "The back squat loads the whole lower body through a deep knee and hip bend, training the quads and glutes while demanding bracing and balance from the trunk. Done well it is one of the most transferable strength exercises there is; done poorly it is where most technique faults show up first.",
  demoCaption: "Side-on demonstration — descend to depth, drive through mid-foot to stand.",
  steps: [
    {
      phase: "Setup",
      body: "Set the bar in the rack at roughly mid-chest height. Grip evenly, step under, and place the bar across the upper traps (high-bar) or rear delts (low-bar). Brace, unrack with a short step back, and settle your stance.",
      cues: ["Bar centred on the back, not the neck", "Elbows down, chest tall", "Two steps back, no more"],
    },
    {
      phase: "Starting Position",
      body: "Feet about shoulder-width, toes turned out 10–30°. Screw your feet into the floor to build tension in the hips. Take a big breath into the belly and brace as if bracing for a punch.",
      cues: ["Feet flat, tripod contact", "Ribs stacked over pelvis", "360° brace before you move"],
    },
    {
      phase: "Execution",
      body: "Begin by breaking at the hips and knees together, sitting between your feet rather than folding forward. Track the knees out over the toes and keep the bar travelling in a straight vertical line over the mid-foot.",
      cues: ["Hips and knees bend together", "Knees track over toes", "Bar path stays over mid-foot"],
    },
    {
      phase: "Top Position",
      body: "Descend until the hip crease drops below the top of the knee (parallel or just below), keeping a neutral spine. This is the deepest point; your torso angle should match your build and stance.",
      cues: ["Hips below knee crease", "Neutral spine held", "No collapse at the bottom"],
    },
    {
      phase: "Eccentric (lowering)",
      body: "The descent is controlled, not dropped. Lower under tension so the muscles stay loaded and the bottom position is stable and reversible — never bounce off the bottom with a loss of bracing.",
      cues: ["Control the descent", "Stay braced throughout", "Reach depth without relaxing"],
    },
    {
      phase: "Breathing",
      body: "Use the Valsalva pattern: breathe in and brace at the top, hold the breath through the descent and the hardest part of the ascent (the sticking point), then exhale once past it. Re-breathe and re-brace each rep.",
      cues: ["Inhale + brace at the top", "Hold through the sticking point", "Exhale after the hardest part"],
    },
    {
      phase: "Tempo",
      body: "A controlled 2–3 second descent, a brief pause or immediate reversal at depth, then a powerful stand. Avoid rushing the eccentric — most depth and stability faults come from descending too fast.",
      cues: ["~2–3s down", "No bounce", "Explosive but controlled up"],
    },
  ],
  biomechanics: [
    {
      title: "Hip and knee share the load",
      body: "The squat is a simultaneous hip and knee extension. How upright you stay depends on limb lengths and stance — a longer femur forces more forward lean, which is normal, not a fault.",
    },
    {
      title: "The bar wants to stay over mid-foot",
      body: "Balance is maintained by keeping the barbell stacked vertically over the mid-foot. If the bar drifts forward of that line, the back has to work harder and the lift feels heavier than it is.",
    },
    {
      title: "Knees travelling forward is normal",
      body: "Deep squatting requires the knees to move in front of the toes; this is safe with good tracking. Blocking forward knee travel just shifts stress to the lower back.",
    },
    {
      title: "Depth is a range-of-motion signal",
      body: "Reaching at least parallel puts the glutes and adductors through a fuller range. Consistent depth is one of the clearest markers of a well-controlled squat.",
    },
  ],
  mistakes: [
    {
      title: "Knees caving inward (valgus)",
      why: "Weak or under-cued hip external rotators and adductors, or driving up too fast under load.",
      impact: "Concentrates stress on the inside of the knee and leaks force, making the lift less efficient and raising ligament strain over time.",
      fix: "Cue 'spread the floor' — actively push the knees out to track over the toes. Strengthen with banded squats and pause reps at lighter loads.",
    },
    {
      title: "Heels lifting / weight on the toes",
      why: "Limited ankle mobility or an over-forward bar path, so balance shifts onto the forefoot.",
      impact: "Destabilises the base and pitches the torso forward, overloading the lower back and shortening depth.",
      fix: "Keep a tripod foot and think 'drive through the whole foot'. Improve ankle mobility, or elevate the heels slightly with lifting shoes.",
    },
    {
      title: "Not reaching depth",
      why: "Load too heavy, mobility restrictions, or simply stopping early out of habit.",
      impact: "Trains a shorter range, under-develops the glutes and hides whether you can control the bottom position.",
      fix: "Reduce the load and squat to a consistent target (e.g. box or parallel), then rebuild. Confirm depth from a side-on view.",
    },
    {
      title: "Good-morning squat (hips shoot up first)",
      why: "Quads give out or bracing is lost, so the hips rise faster than the shoulders and the squat becomes a back extension.",
      impact: "Shifts load off the legs and onto the spinal erectors, greatly increasing lower-back stress.",
      fix: "Lighten the load, keep the chest and hips rising together, and build quad strength with tempo and pause squats.",
    },
    {
      title: "Losing the brace at the bottom",
      why: "Exhaling early or relaxing the trunk to reach depth.",
      impact: "Removes the intra-abdominal pressure that protects the spine and stabilises the load right where it's most vulnerable.",
      fix: "Hold the breath from the top through the sticking point. Practise the 360° brace before unracking each set.",
    },
    {
      title: "Butt wink (posterior pelvic tilt at depth)",
      why: "Squatting past your controllable range so the pelvis tucks under.",
      impact: "Rounds the lower spine under load; occasional and small it's minor, but repeated deep and heavy it adds shear stress.",
      fix: "Squat only as deep as you can keep a neutral pelvis, widen the stance a touch, and work on hip and ankle mobility.",
    },
    {
      title: "Bar drifting forward",
      why: "Descending onto the toes or an over-vertical shin with a weak upper back.",
      impact: "Moves the load ahead of the mid-foot, forcing the back to compensate and making heavy squats feel crushing.",
      fix: "Keep the mid-foot under the bar and the upper back tight; film side-on to check the bar path stays vertical.",
    },
  ],
  aiFocus: [
    { label: "Squat depth (ROM)", detail: "Measures hip-crease-to-knee height at the bottom to confirm you reach at least parallel, rep to rep." },
    { label: "Knee tracking & valgus", detail: "Watches for the knees caving inward relative to the toes during the drive out of the hole." },
    { label: "Left/right symmetry", detail: "Compares hip and knee angles side to side to flag a dominant leg or an uneven descent." },
    { label: "Torso & bar path", detail: "Tracks trunk lean and estimated bar path to see whether load stays balanced over the mid-foot." },
    { label: "Tempo & control", detail: "Times the eccentric and detects bouncing so it can tell a controlled rep from a dropped one." },
    { label: "Depth consistency", detail: "Checks that later reps hold the same depth as the first — a key sign of fatigue creeping in." },
  ],
  coaching: [
    {
      level: "Beginner",
      tips: [
        "Master the pattern with just the bar or bodyweight before loading.",
        "Squat to a box set at parallel to groove consistent, safe depth.",
        "Film every working set from the side so you can see depth and bar path.",
      ],
    },
    {
      level: "Intermediate",
      tips: [
        "Add pause squats (2–3s at depth) to build control and confidence in the hole.",
        "Use tempo eccentrics to expose and fix stability faults.",
        "Keep most working sets 2–3 reps shy of failure to protect technique.",
      ],
    },
    {
      level: "Advanced",
      tips: [
        "Cycle intensity with blocks of heavier low-rep and higher-rep volume work.",
        "Use specific variations (pin squats, tempo, pause) to target your personal sticking point.",
        "Autoregulate load with RPE so technique stays sharp on hard days.",
      ],
    },
  ],
  safety: [
    "Always squat inside a rack with the safety pins set just below your bottom position.",
    "Learn to bail safely — with a high-bar squat you can dump the bar backwards off the shoulders.",
    "Warm up the hips, knees and ankles and ramp the load gradually.",
    "Stop a set if you lose your brace or your depth collapses — leave reps in reserve.",
    "If you feel sharp knee or lower-back pain (not muscular fatigue), rack the bar and reassess.",
  ],
  faqs: [
    { q: "How deep should I squat?", a: "Aim for at least parallel — hip crease level with or just below the top of the knee — as long as you can keep a neutral spine. Depth beyond that is fine if you control it." },
    { q: "Are knees past toes dangerous?", a: "No. For most people the knees must travel forward of the toes to squat deep, and that's safe with good tracking. Artificially blocking it just overloads the back." },
    { q: "High-bar or low-bar?", a: "High-bar keeps a more upright torso and emphasises the quads; low-bar allows more weight with more hip drive. Pick the one you can perform consistently and comfortably." },
    { q: "Should I use a belt?", a: "A belt gives your brace something to push against and can help on heavy sets, but learn to brace without one first so the belt adds to a skill you already have." },
    { q: "Why do my heels lift?", a: "Usually limited ankle mobility or the weight drifting onto your toes. Work on ankle mobility, keep the whole foot planted, or try a slightly raised heel." },
  ],
  related: ["conventional-deadlift", "bench-press"],
};

export default guide;
