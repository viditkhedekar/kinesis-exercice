import type { GuideData } from "../types";

const guide: GuideData = {
  slug: "dumbbell-bicep-curl",
  name: "Dumbbell Bicep Curl",
  exerciseKey: "bicep_curl",
  category: "Upper body · Dumbbell",
  difficulty: "Beginner",
  equipment: ["Dumbbells"],
  primaryMuscles: ["Biceps brachii", "Brachialis"],
  secondaryMuscles: ["Brachioradialis", "Forearm flexors", "Anterior deltoid"],
  summary:
    "A single-joint elbow flexion that isolates the biceps — simple to learn, easy to cheat, and highly responsive to strict, full-range reps.",
  intro:
    "The dumbbell curl trains the biceps through elbow flexion and supination. Because it's a small, isolated movement, the difference between an average and an excellent curl is almost entirely control: keeping the upper arm still and moving through a full, deliberate range.",
  demoCaption: "Front-on demonstration — curl both arms to a full squeeze, lower under control.",
  steps: [
    {
      phase: "Setup",
      body: "Stand tall with a dumbbell in each hand, arms at your sides, palms facing in. Set your feet hip-width and brace your trunk so the torso stays still.",
      cues: ["Tall posture, ribs down", "Neutral wrists", "Trunk braced"],
    },
    {
      phase: "Starting Position",
      body: "Begin with the arms fully extended, elbows pinned to your sides and just in front of the ribs. Shoulders stay down and back — only the forearms should move.",
      cues: ["Elbows pinned to the sides", "Arms fully straight", "Shoulders relaxed and back"],
    },
    {
      phase: "Execution",
      body: "Curl the weight by flexing the elbow, rotating the palm up (supinating) as you rise. Keep the upper arm vertical and still so the biceps do the work.",
      cues: ["Flex the elbow, supinate", "Upper arm stays vertical", "No swinging"],
    },
    {
      phase: "Top Position",
      body: "Finish with the palm up and the biceps fully contracted, forearm close to the upper arm. Squeeze for a beat without letting the elbow drift forward.",
      cues: ["Full contraction, palm up", "Squeeze for a beat", "Elbow stays put"],
    },
    {
      phase: "Eccentric (lowering)",
      body: "Lower slowly and fully until the arm is straight again. The eccentric is where much of the biceps growth happens — resist the weight rather than dropping it.",
      cues: ["Slow, controlled descent", "Lower to full extension", "Stay in control"],
    },
    {
      phase: "Breathing",
      body: "Breathe out as you curl up and in as you lower. Keep a light brace so the breath doesn't turn into torso swing.",
      cues: ["Exhale up", "Inhale down", "Light, steady brace"],
    },
    {
      phase: "Tempo",
      body: "Curl up in about a second, then take 2–3 seconds to lower. Slowing the eccentric and pausing at the top is far more effective than adding weight you have to swing.",
      cues: ["~1s up", "~2–3s down", "Pause at the top"],
    },
  ],
  biomechanics: [
    { title: "It's an isolation movement", body: "The curl works one joint — the elbow. Because the muscle is small and the lever short, keeping strict form matters more than loading heavy." },
    { title: "Supination adds contraction", body: "Rotating the palm up as you curl fully engages the biceps, which both flexes the elbow and supinates the forearm. A neutral (hammer) grip shifts work toward the brachialis and forearm." },
    { title: "The upper arm is the anchor", body: "Keeping the upper arm still forces the biceps to move the load. Let the elbow drift forward and the front delt takes over, shortening the tension on the biceps." },
    { title: "Tension favours a full range", body: "Straightening fully at the bottom stretches the biceps under load, and squeezing at the top maximises contraction — both ends of the range drive the training effect." },
  ],
  mistakes: [
    {
      title: "Swinging with the torso",
      why: "Using momentum from the back and hips to move a weight that's too heavy.",
      impact: "Takes tension off the biceps and loads the lower back, so you work the target muscle less while risking strain.",
      fix: "Lighten the load, brace the trunk, and keep the torso motionless — if you have to swing, it's too heavy.",
    },
    {
      title: "Elbows drifting forward",
      why: "Letting the shoulder flex to help lift, especially near the top.",
      impact: "Recruits the front delt and shortens the biceps' line of pull, reducing the stimulus.",
      fix: "Pin the elbows to your sides just in front of the ribs; only the forearm should move.",
    },
    {
      title: "Partial range of motion",
      why: "Stopping short at the bottom or the top, often to keep constant tension with heavier weight.",
      impact: "Under-trains the stretched and fully-contracted positions where the biceps develops most.",
      fix: "Straighten fully at the bottom and squeeze fully at the top with a load you can control through the whole range.",
    },
    {
      title: "Rushing the eccentric",
      why: "Dropping the weight quickly to save effort on each rep.",
      impact: "Skips the most growth-productive part of the rep and reduces control.",
      fix: "Take 2–3 seconds to lower each rep, resisting the weight the whole way down.",
    },
    {
      title: "Uneven arms",
      why: "One biceps is stronger, so it leads or lifts more when both arms curl together.",
      impact: "Reinforces the imbalance and lets the weaker arm short-change its range.",
      fix: "Curl to a shared tempo, or train one arm at a time so each gets equal, full-range work.",
    },
    {
      title: "Bending the wrist",
      why: "Trying to squeeze extra range by curling the wrist instead of the elbow.",
      impact: "Strains the wrist and shifts effort to the forearms.",
      fix: "Keep a neutral, stacked wrist and drive the movement purely from the elbow.",
    },
  ],
  aiFocus: [
    { label: "Elbow range of motion", detail: "Measures elbow flexion from full extension to full squeeze to confirm you use the whole range." },
    { label: "Upper-arm stability", detail: "Detects the elbow drifting forward or the upper arm swinging, which signals shoulder assistance." },
    { label: "Left/right symmetry", detail: "Compares both arms' range and timing to flag a dominant side or out-of-sync curls." },
    { label: "Torso posture", detail: "Watches for trunk swing and lean that indicate momentum cheating." },
    { label: "Tempo & control", detail: "Times the lowering phase to reward a controlled eccentric over dropped reps." },
    { label: "Timing symmetry", detail: "Checks that both arms reach the top together rather than one finishing early." },
  ],
  coaching: [
    {
      level: "Beginner",
      tips: [
        "Start light enough to keep the torso still and the elbows pinned.",
        "Film front-on so you can see both arms moving evenly.",
        "Prioritise a full range over the number on the dumbbell.",
      ],
    },
    {
      level: "Intermediate",
      tips: [
        "Add slow eccentrics and a top-end squeeze to increase the stimulus without more weight.",
        "Rotate in hammer and incline curls to train the arm at different lengths.",
        "Train each arm to the same range — fix imbalances with unilateral work.",
      ],
    },
    {
      level: "Advanced",
      tips: [
        "Use tempo and pause variations to intensify without heaving heavier loads.",
        "Manage total elbow-flexion volume across curls, rows and pulldowns to recover.",
        "Progress by adding controlled range and reps before adding weight.",
      ],
    },
  ],
  safety: [
    "The curl is low-risk, but heavy swinging can strain the lower back and elbow tendons.",
    "Warm up the elbows, especially in colder conditions, before heavier sets.",
    "Avoid fully snapping the elbow into extension under a heavy load — control the bottom.",
    "If you feel elbow-tendon pain, reduce load and slow the tempo rather than pushing through.",
  ],
  faqs: [
    { q: "Should I curl both arms together or alternate?", a: "Both work. Curling together is time-efficient and lets the AI compare symmetry; alternating or single-arm work is great for fixing an imbalance." },
    { q: "Do I need to fully straighten my arm?", a: "Yes — straightening at the bottom loads the biceps in a stretched position, which is important for growth. Just control the descent rather than letting it snap." },
    { q: "Why keep my elbows pinned?", a: "It stops the front delt taking over. If the elbows drift forward, the shoulder does the lifting and the biceps get less work." },
    { q: "Is heavier always better?", a: "No. Past a point, more weight means more swinging and less biceps tension. Strict full-range reps beat heavier cheated ones for this muscle." },
    { q: "Hammer curls or regular curls?", a: "Regular (supinated) curls emphasise the biceps; hammer (neutral) curls shift work to the brachialis and forearm. Both are useful — rotate them." },
  ],
  related: ["dumbbell-lateral-raise", "bench-press"],
};

export default guide;
