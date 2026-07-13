import type { GuideData } from "../types";

const guide: GuideData = {
  slug: "conventional-deadlift",
  name: "Conventional Deadlift",
  exerciseKey: "deadlift",
  category: "Full body · Barbell",
  difficulty: "Advanced",
  equipment: ["Barbell", "Weight plates"],
  primaryMuscles: ["Gluteus maximus", "Hamstrings", "Erector spinae"],
  secondaryMuscles: ["Quadriceps", "Lats", "Trapezius", "Forearms"],
  summary:
    "A ground-to-hip hinge that trains the entire posterior chain and teaches you to move heavy loads with a braced, neutral spine.",
  intro:
    "The deadlift is the purest expression of a hip hinge under maximal load: the bar starts on the floor and finishes at the hips, driven by the glutes, hamstrings and back working as one. It rewards patience and position, and punishes rushing off the floor.",
  demoCaption: "Side-on demonstration — take the slack out, push the floor away, lock out tall.",
  steps: [
    {
      phase: "Setup",
      body: "Stand with the bar over mid-foot, roughly hip-width, shins an inch or two away. Bend at the hips to grip just outside the knees. The bar should nearly touch your shins.",
      cues: ["Bar over mid-foot", "Hip-width stance", "Grip just outside the knees"],
    },
    {
      phase: "Starting Position",
      body: "Drop the hips until the shins meet the bar, lift the chest to set a neutral spine, and pull your shoulder blades over the bar. Take the slack out of the bar — feel it engage the plates — before you pull.",
      cues: ["Neutral spine, chest set", "Shoulders slightly ahead of the bar", "'Take the slack out'"],
    },
    {
      phase: "Execution",
      body: "Push the floor away with your legs while keeping the bar dragging up the shins. Hips and shoulders rise together; the bar travels in a straight vertical line close to the body.",
      cues: ["Push the floor away", "Bar stays against the legs", "Hips and shoulders rise together"],
    },
    {
      phase: "Top Position",
      body: "Finish standing tall with hips fully extended, glutes squeezed and ribs down — no leaning back. Lockout is a straight, stacked line from head to heels, not a hyperextension.",
      cues: ["Stand tall, glutes locked", "Ribs down, no lean-back", "Neutral neck"],
    },
    {
      phase: "Eccentric (lowering)",
      body: "Reverse the path: push the hips back first, then bend the knees once the bar passes them. Keep it close to the body and controlled — the descent is part of the lift, not a drop.",
      cues: ["Hips back first", "Bar close to the legs", "Control it down"],
    },
    {
      phase: "Breathing",
      body: "Take a big breath and brace hard before the bar leaves the floor. Hold it through the pull, then exhale at lockout or reset your breath at the top between reps.",
      cues: ["Brace before you pull", "Hold through the lift", "Reset breath each rep"],
    },
    {
      phase: "Tempo",
      body: "Deadlifts are grind-strength: a deliberate build off the floor and a controlled return. Reset your position on every rep rather than bouncing plates off the ground (touch-and-go only when trained deliberately).",
      cues: ["Deliberate off the floor", "Controlled descent", "Full reset between reps"],
    },
  ],
  biomechanics: [
    { title: "It's a hinge, not a squat", body: "The deadlift is a hip-dominant hinge: most of the movement is hip extension with the hips set higher than in a squat. Trying to 'squat' the bar up puts the knees in the bar's path." },
    { title: "Keep the bar over mid-foot", body: "The most efficient bar path is a straight vertical line over the mid-foot. Any horizontal drift away from the body lengthens the lever on the lower back and makes the weight feel far heavier." },
    { title: "The lats keep the bar in", body: "Engaging the lats ('protect your armpits') holds the bar against the body and keeps the spine braced, shortening the lever and improving efficiency." },
    { title: "Neutral spine transmits force", body: "A braced, neutral spine lets force from the legs and hips travel to the bar. Rounding under heavy load raises shear stress and leaks power." },
  ],
  mistakes: [
    {
      title: "Rounding the lower back",
      why: "Hips set too high, weak bracing, or a load beyond your current position strength.",
      impact: "Adds shear stress to the lumbar spine and is the most common source of deadlift back injury.",
      fix: "Set the chest and brace before pulling, reduce the load, and reinforce position with tempo and paused deficit work.",
    },
    {
      title: "Hips shooting up first",
      why: "Legs disengage early or the setup hips are too low, so the bar can't move until the hips rise.",
      impact: "Turns the lift into a stiff-legged back extension, overloading the erectors and stalling heavy pulls.",
      fix: "Set the hips higher to start, and think 'push the floor away' so the legs and hips extend together.",
    },
    {
      title: "Bar drifting away from the body",
      why: "Weak lats or leaning back too early, letting the bar swing forward.",
      impact: "Lengthens the lever arm on the spine and dramatically increases lower-back load.",
      fix: "Squeeze the lats to keep the bar brushing the legs, and think of dragging the bar up your shins and thighs.",
    },
    {
      title: "Starting with slack in the bar",
      why: "Yanking the bar off the floor before tension is built between you and the barbell.",
      impact: "Produces a jarring, unbraced initial pull where the back can round under a sudden load spike.",
      fix: "'Take the slack out' — pull up gently until the bar engages the plates and your body is tight, then drive.",
    },
    {
      title: "Hyperextending at lockout",
      why: "Over-cueing 'squeeze' and leaning the torso back past vertical.",
      impact: "Loads the lumbar spine in extension at the top for no benefit.",
      fix: "Finish tall with ribs down and glutes squeezed — a straight stacked line, not a lean-back.",
    },
    {
      title: "Knees caving on the drive",
      why: "Under-active hip external rotators or pushing up too aggressively.",
      impact: "Leaks force and stresses the knees, especially as fatigue sets in on later reps.",
      fix: "Cue 'knees out, spread the floor' as you initiate the pull; strengthen the hips with paused and lighter work.",
    },
    {
      title: "Mixed-grip over-reliance",
      why: "Using an alternating grip on every set instead of building grip or using straps for volume.",
      impact: "Can create asymmetry and, in rare cases, biceps strain on the supinated arm.",
      fix: "Use a double-overhand or hook grip for lighter sets, alternate which hand supinates, and use straps for heavy back-off volume.",
    },
  ],
  aiFocus: [
    { label: "Spinal position", detail: "Tracks the back angle through the pull to flag lumbar rounding as the bar breaks the floor." },
    { label: "Hip-shoulder timing", detail: "Detects the hips rising faster than the shoulders — the classic 'stripper' deadlift fault." },
    { label: "Bar path", detail: "Estimates how vertical and close to the body the bar travels from floor to lockout." },
    { label: "Lockout quality", detail: "Checks for full hip extension without hyperextension or leaning back at the top." },
    { label: "Left/right symmetry", detail: "Compares side-to-side hip and shoulder movement to spot an uneven pull." },
    { label: "Range of motion", detail: "Confirms the bar reaches the floor and a complete lockout on every rep." },
  ],
  coaching: [
    {
      level: "Beginner",
      tips: [
        "Learn the hinge with Romanian deadlifts and light pulls before going heavy.",
        "Pull from blocks or elevated plates if you can't reach the floor with a neutral spine.",
        "Reset every rep — treat each pull as a fresh, deliberate lift.",
      ],
    },
    {
      level: "Intermediate",
      tips: [
        "Add paused or tempo deadlifts to reinforce position off the floor.",
        "Build grip with double-overhand holds before defaulting to straps.",
        "Keep heavy sets crisp; stop the set the moment position degrades.",
      ],
    },
    {
      level: "Advanced",
      tips: [
        "Use deficit pulls or block pulls to attack your specific sticking point.",
        "Cycle intensity in blocks and manage total pulling volume to recover well.",
        "Autoregulate with RPE — deadlifts punish grinding junk reps more than most lifts.",
      ],
    },
  ],
  safety: [
    "Prioritise a neutral spine over lifting more weight — always.",
    "Deadlift on a flat, stable surface with plates that let the bar sit at the right height.",
    "It's fine to simply set a heavy bar down rather than fight a rep with a rounding back.",
    "Warm up the hips and hamstrings and ramp load progressively.",
    "Sharp lower-back or hamstring-insertion pain means stop and reassess your setup.",
  ],
  faqs: [
    { q: "Should the bar touch the floor every rep?", a: "For strict deadlifts, yes — reset each rep. Touch-and-go can build volume but only once you can keep position under the reactive load." },
    { q: "Conventional or sumo?", a: "Both are valid. Conventional demands more from the back and hamstrings; sumo shortens the range and involves more of the quads and hips. Choose based on leverages and comfort." },
    { q: "Is a rounded upper back okay?", a: "A slightly rounded upper back (thoracic) is common among strong pullers and generally tolerated. It's lower-back (lumbar) rounding under load that you want to avoid." },
    { q: "Do I need a belt?", a: "A belt can support heavier pulls by reinforcing your brace, but build the ability to brace hard without one first." },
    { q: "Why does the bar drift away from me?", a: "Usually weak lat engagement or leaning back early. Keep the lats tight and drag the bar up your legs so it never swings forward." },
  ],
  related: ["barbell-back-squat", "bench-press"],
};

export default guide;
