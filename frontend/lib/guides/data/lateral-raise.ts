import type { GuideData } from "../types";

const guide: GuideData = {
  slug: "dumbbell-lateral-raise",
  name: "Dumbbell Lateral Raise",
  exerciseKey: "lateral_raise",
  category: "Upper body · Dumbbell",
  difficulty: "Beginner",
  equipment: ["Dumbbells"],
  primaryMuscles: ["Lateral deltoid"],
  secondaryMuscles: ["Anterior deltoid", "Posterior deltoid", "Trapezius", "Supraspinatus"],
  summary:
    "A shoulder-abduction isolation that builds width through the side delts — light on load, but unforgiving of momentum and posture.",
  intro:
    "The lateral raise trains the side deltoid by lifting the arms out to the sides. It's the classic movement for shoulder width, and it's a precision exercise: small changes in path, tempo and trap involvement completely change which muscle does the work.",
  demoCaption: "Front-on demonstration — raise both arms to shoulder height, lower under control.",
  steps: [
    {
      phase: "Setup",
      body: "Stand tall with a dumbbell in each hand at your sides, palms facing in. Feet hip-width, a slight bend in the elbows, torso braced.",
      cues: ["Tall, braced posture", "Soft elbows", "Palms facing in"],
    },
    {
      phase: "Starting Position",
      body: "Let the arms hang with a soft, fixed elbow bend and a slight forward lean at the shoulders. Depress the shoulder blades so you don't start by shrugging.",
      cues: ["Shoulders down, not shrugged", "Fixed soft-elbow angle", "Dumbbells just off the thighs"],
    },
    {
      phase: "Execution",
      body: "Raise the dumbbells out to the sides, leading with the elbows, until the upper arms reach roughly shoulder height. Think of pouring water from the little-finger side to bias the side delt.",
      cues: ["Lead with the elbows", "Raise out to the sides", "Little-finger side leads slightly"],
    },
    {
      phase: "Top Position",
      body: "Stop when the upper arms are about parallel to the floor — hands level with or just below the elbows. Going much higher hands the work to the traps.",
      cues: ["Upper arms ~parallel to floor", "Elbows level with or above hands", "No shrug at the top"],
    },
    {
      phase: "Eccentric (lowering)",
      body: "Lower slowly and under control back to the start, resisting gravity the whole way. Don't let the weights drop — the descent keeps the side delt under tension.",
      cues: ["Slow, controlled descent", "Resist the weight", "Full range back down"],
    },
    {
      phase: "Breathing",
      body: "Exhale as you raise, inhale as you lower. Keep the breath quiet and the trunk still so it doesn't turn into a whole-body heave.",
      cues: ["Exhale up", "Inhale down", "Torso stays still"],
    },
    {
      phase: "Tempo",
      body: "Raise in about a second, hold briefly at the top, then lower over 2–3 seconds. Slow and strict with light weight beats fast and heavy with momentum every time.",
      cues: ["~1s up", "Brief hold at the top", "~2–3s down"],
    },
  ],
  biomechanics: [
    { title: "Abduction targets the side delt", body: "Raising the arm out to the side (abduction) is the side deltoid's primary job. Keeping the movement in the frontal plane keeps the tension where you want it." },
    { title: "Leading with the elbow biases the delt", body: "If the hands lead and rise above the elbows, the movement rotates and the traps take over. Leading with the elbow keeps the side delt working." },
    { title: "Traps take over past shoulder height", body: "Above roughly parallel, the shoulder blade rotates upward and the traps drive the movement. Stopping at shoulder height keeps the emphasis on the delt." },
    { title: "Light loads, long levers", body: "With a straight-ish arm, the dumbbell sits far from the shoulder, creating a long lever. That's why lateral raises feel heavy with little weight — and why momentum is so tempting." },
  ],
  mistakes: [
    {
      title: "Using momentum / swinging",
      why: "The weight is too heavy, so the hips and torso heave it up.",
      impact: "Takes tension off the side delt and can strain the lower back — you train everything except the target muscle.",
      fix: "Drop the weight substantially and raise with a still torso; if you have to swing, it's too heavy.",
    },
    {
      title: "Shrugging the traps",
      why: "Starting from an elevated shoulder or raising above shoulder height.",
      impact: "Shifts the work from the side delt to the upper traps, defeating the purpose of the exercise.",
      fix: "Depress the shoulder blades before you lift and stop at shoulder height; think 'long neck'.",
    },
    {
      title: "Raising the hands above the elbows",
      why: "Leading with the hands or internally rotating the arm at the top.",
      impact: "Rotates the shoulder and can pinch the joint (impingement), while reducing side-delt tension.",
      fix: "Lead with the elbows and keep the hands level with or just below them throughout.",
    },
    {
      title: "Going too high",
      why: "Chasing a bigger range by lifting well past parallel.",
      impact: "Hands the movement to the traps and increases shoulder-joint stress at the top.",
      fix: "Stop when the upper arms reach roughly parallel to the floor.",
    },
    {
      title: "Straightening the elbow under load",
      why: "Letting the arm extend to lengthen the lever, usually as fatigue sets in.",
      impact: "Massively increases stress at the elbow and shoulder for the given weight.",
      fix: "Set a soft elbow bend at the start and keep that same angle for the whole rep.",
    },
    {
      title: "Dropping the eccentric",
      why: "Letting the weights fall quickly to reset for the next rep.",
      impact: "Skips a big share of the muscle-building tension and reduces control.",
      fix: "Lower over 2–3 seconds, staying in control to the bottom.",
    },
    {
      title: "Uneven arms",
      why: "One delt is stronger and leads, or posture is tilted to one side.",
      impact: "Reinforces an imbalance and lets the weaker side under-work.",
      fix: "Raise both arms to the same height on a shared count, or train single-arm to even them out.",
    },
  ],
  aiFocus: [
    { label: "Raise height (ROM)", detail: "Measures how far the arms abduct to confirm you reach about shoulder height without overshooting into the traps." },
    { label: "Left/right symmetry", detail: "Compares both arms' height and path to flag a dominant side or an uneven raise." },
    { label: "Trap involvement / shrug", detail: "Watches shoulder elevation to detect shrugging that takes over from the side delt." },
    { label: "Torso posture", detail: "Detects trunk lean and swing that signal momentum rather than strict delt work." },
    { label: "Tempo & control", detail: "Times the descent to reward a controlled eccentric over dropped reps." },
    { label: "Arm path", detail: "Checks the arms stay out to the sides (frontal plane) rather than drifting forward." },
  ],
  coaching: [
    {
      level: "Beginner",
      tips: [
        "Start lighter than you think — good lateral raises use surprisingly little weight.",
        "Film front-on to check both arms reach the same height and stop at parallel.",
        "Set the shoulders down before each set so the traps don't take over.",
      ],
    },
    {
      level: "Intermediate",
      tips: [
        "Add a pause at the top and a slow eccentric to intensify without more load.",
        "Try a slight forward lean or cable variation to keep tension through the whole range.",
        "Even out sides with single-arm sets when one delt lags.",
      ],
    },
    {
      level: "Advanced",
      tips: [
        "Use lengthened partials or drop sets to add stimulus once strict full reps are easy.",
        "Manage shoulder volume across pressing and raising to avoid overuse.",
        "Progress by adding strict reps and range before adding weight.",
      ],
    },
  ],
  safety: [
    "Keep raises at or below shoulder height to protect the shoulder joint.",
    "Avoid internally rotating the arm (thumbs sharply down) at the top, which can pinch the shoulder.",
    "Warm the shoulders up thoroughly before your working sets.",
    "If you feel a pinch at the top of the raise, lower your end range and check your arm path.",
  ],
  faqs: [
    { q: "How high should I raise the dumbbells?", a: "To roughly shoulder height — upper arms about parallel to the floor. Higher than that shifts the work to the traps and stresses the shoulder." },
    { q: "Why does such a light weight feel so hard?", a: "With a near-straight arm, the dumbbell sits far from the shoulder, creating a long lever. That's normal — resist the urge to add weight you can only swing." },
    { q: "Should my arm be straight or bent?", a: "Keep a fixed, soft bend in the elbow throughout. A locked straight arm overloads the joint; a changing bend turns it into a different movement." },
    { q: "Why do I feel it in my traps?", a: "Usually because you start shrugged or raise above shoulder height. Depress the shoulder blades first and stop at parallel to keep the side delt working." },
    { q: "Cable or dumbbell?", a: "Both are great. Cables keep tension more constant through the range; dumbbells are simple and let the AI compare left and right symmetry easily." },
  ],
  related: ["dumbbell-bicep-curl", "bench-press"],
};

export default guide;
