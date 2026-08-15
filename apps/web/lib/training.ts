/**
 * The articled-clerk walkthrough: one fictional matter, taken in the order a
 * district practice actually takes it.
 *
 * The point of the module is sequence. A student knows what a plaint is; what
 * they do not know is that limitation is computed before anyone drafts, and
 * that the workspace will not open a matter until a conflict check has been
 * decided. Every gate here mirrors a constraint the product already enforces
 * or a rule the practice already follows — nothing is invented for the lesson.
 */

/** The brief the student works from. Fictional, and labelled as such in the UI. */
export const BRIEF = {
  client: "ABC Manufacturing Private Limited",
  opponent: "Northstar Services Private Limited",
  forum: "District Court, Pune",
  claimValue: 3400000,
  /** The date the contract was broken — the trigger for Article 55. */
  breachDate: "2023-03-12",
  summary:
    "ABC engaged Northstar to maintain its plant software under a two-year agreement. Northstar stopped attending site on 12 March 2023 and has not returned. ABC paid two quarters in advance and wants compensation. The partner has handed you the file and asked you to take it from intake to the first hearing.",
} as const;

export type Option = { id: string; label: string };

export type Gate =
  /** One right answer. */
  | { kind: "single"; options: Option[]; correct: string }
  /** A set — partial credit does not unlock the step. */
  | { kind: "multi"; options: Option[]; correct: string[] }
  /** A sequence the student assembles by clicking in order. */
  | { kind: "order"; options: Option[]; correct: string[] }
  /**
   * A date the student must arrive at themselves. Checked against the
   * limitation engine at /tools/limitation-periods, not a stored constant, so
   * the answer and the app's own calculator can never drift apart.
   */
  | { kind: "computed-date"; triggerDate: string; periodValue: number; periodUnit: "years" };

export type Step = {
  key: string;
  /** Shown in the rail: what a clerk would call this stage. */
  stage: string;
  title: string;
  /** The instruction the student acts on. */
  prompt: string;
  gate: Gate;
  /** Revealed only once the gate opens. */
  why: string;
  /** What the rule rests on. "Practice" where there is no provision to cite. */
  authority: string;
  /** Nudge shown on a wrong answer. Never gives the answer away. */
  hint: string;
};

export const STEPS: Step[] = [
  {
    key: "intake",
    stage: "Intake",
    title: "Before the matter exists",
    prompt:
      "The file lands on your desk. What has to happen before a matter can be opened for ABC against Northstar?",
    gate: {
      kind: "single",
      options: [
        {
          id: "conflict-first",
          label:
            "Run a conflict check against the client and every related party, and record the decision on file.",
        },
        {
          id: "open-then-check",
          label: "Open the matter now so time is not lost, and run the conflict check before the first hearing.",
        },
        {
          id: "only-if-acted",
          label: "A conflict check is only needed if the firm has acted for the other side before.",
        },
        {
          id: "client-word",
          label: "Take the client's confirmation that there is no conflict and note it on the file.",
        },
      ],
      correct: "conflict-first",
    },
    why:
      "The check comes first because its whole purpose is to decide whether the firm may take the work at all — running it after the matter is open asks a question the firm has already answered by acting. This workspace enforces the same order: the API refuses to create a matter under a client until a conflict check exists and has been decided, which is why the seeded demo has to raise one and clear it before the matter appears.",
    authority: "Bar Council of India Rules, Part VI, Chapter II — an advocate's duty to the client.",
    hint: "Ask what the check is for. If the answer arrives after the firm has already started acting, what has it decided?",
  },
  {
    key: "limitation",
    stage: "Limitation",
    title: "Is there a suit at all?",
    prompt:
      `Northstar stopped performing on ${BRIEF.breachDate.split("-").reverse().join("/")}. This is a suit for compensation for breach of contract, so Article 55 of the Limitation Act gives three years from the date the contract is broken. Work out the last date on which the plaint can be filed, and enter it.`,
    gate: { kind: "computed-date", triggerDate: BRIEF.breachDate, periodValue: 3, periodUnit: "years" },
    why:
      "Limitation is computed before anyone drafts, because it decides whether there is a suit to draft. Section 3 makes this the court's own duty: a suit filed after the period is dismissed even where limitation is not pleaded as a defence, so no amount of good drafting rescues a late plaint. Where the last day falls on a court holiday, the Act allows filing on the next day the court reopens — the calculator applies that adjustment for you.",
    authority: "Limitation Act, 1963 — s. 3 (bar of limitation), s. 4 (expiry on a court holiday), Article 55 (compensation for breach of contract).",
    hint: "Three years from the trigger date. Count from the day the contract was broken, and check whether the result lands on a working day.",
  },
  {
    key: "court-fee",
    stage: "Valuation",
    title: "The fee you can stand behind",
    prompt:
      `The claim is valued at ₹${BRIEF.claimValue.toLocaleString("en-IN")}. Which of these can you rely on for the court-fee figure that goes into the plaint? Select every one that holds.`,
    gate: {
      kind: "multi",
      options: [
        {
          id: "verified-pack",
          label: "A rule pack someone in the firm has verified against this court's current schedule.",
        },
        { id: "demo-pack", label: "The DEMO rule pack that ships with this build." },
        { id: "last-matter", label: "The figure used in a similar matter last year." },
        {
          id: "registry",
          label: "The registry's current fee schedule for the court where you are filing.",
        },
        { id: "opponent", label: "What the other side paid on their counter-claim." },
      ],
      correct: ["verified-pack", "registry"],
    },
    why:
      "Both surviving answers share one property: someone accountable has checked them against the schedule in force for this court, now. A stale figure and a demo figure fail for the same reason, not different ones. The cost of getting it wrong is procedural — a plaint that undervalues the relief or is insufficiently stamped is rejected unless the court's time to correct it is met. This is why the fee engine here refuses to calculate against a pack that has not been marked verified, and why the packs in this build are labelled DEMO ONLY.",
    authority: "Court Fees Act, 1870; CPC Order 7 Rule 11(b) and (c) — rejection of a plaint undervalued or insufficiently stamped.",
    hint: "Two of these hold. Ask of each one: has anybody accountable checked it against the schedule in force for this court, this year?",
  },
  {
    key: "plaint",
    stage: "Drafting",
    title: "What goes in the plaint",
    prompt:
      "You are drafting the plaint. Select everything that must appear in it — and nothing that must not.",
    gate: {
      kind: "multi",
      options: [
        {
          id: "parties",
          label: "The name, description and place of residence of the plaintiff and the defendant.",
        },
        { id: "cause", label: "The facts constituting the cause of action, and when it arose." },
        {
          id: "valuation",
          label: "A statement of the value of the subject matter, for jurisdiction and for court fee.",
        },
        { id: "relief", label: "The relief claimed." },
        { id: "verification", label: "A verification signed by the plaintiff." },
        {
          id: "evidence",
          label: "The evidence by which each fact will be proved at trial.",
        },
        { id: "authorities", label: "The provisions and case law you intend to rely on." },
      ],
      correct: ["parties", "cause", "valuation", "relief", "verification"],
    },
    why:
      "The two you had to leave out are the ones students most often put in. A pleading states material facts, not the evidence by which those facts will be proved, and not the law — the facts are what the other side must answer and what issues are framed from. Evidence comes later, in its own form; argument comes later still. A plaint padded with proof and citation invites an application to strike out, and tells the other side your case.",
    authority: "CPC Order 6 Rule 2 (facts, not evidence), Order 6 Rule 15 (verification), Order 7 Rule 1 (particulars of a plaint).",
    hint: "Five belong. Two describe how you will win rather than what you say happened — and pleadings are for the second.",
  },
  {
    key: "evidence",
    stage: "Evidence",
    title: "Putting a document on record",
    prompt:
      "A signed copy of the agreement has come in from the client. Click the four steps in the order you would take them to get it onto the record and usable.",
    gate: {
      kind: "order",
      options: [
        { id: "bates", label: "Number the pages, so every later reference points somewhere fixed." },
        { id: "index", label: "Enter it in the index with its date, author and where it came from." },
        { id: "file", label: "File it with the plaint, in the list of documents relied on." },
        { id: "exhibit", label: "Have it marked as an exhibit when it is proved." },
      ],
      correct: ["bates", "index", "file", "exhibit"],
    },
    why:
      "The order is forced by what each step depends on. Numbering comes first because every reference made afterwards — in the index, in the plaint, in the brief — points at a page number, and renumbering later silently breaks all of them. The index is what makes the document findable before it is filed. Filing with the plaint is a rule, not a habit: a document the plaintiff sues on and does not file with the plaint may not be received in evidence later without the court's leave. Exhibit marking is last because it happens at proof, in court, not at your desk.",
    authority: "CPC Order 7 Rule 14 (documents relied on filed with the plaint), Order 13 Rule 4 (endorsement on documents admitted in evidence).",
    hint: "Two of these you do at your desk before filing, one is the filing, and one only happens in court. Start with the step that everything else refers back to.",
  },
  {
    key: "brief",
    stage: "Hearing",
    title: "The brief your senior reads in the corridor",
    prompt:
      "First hearing tomorrow. Your senior will read what you hand them in about ninety seconds. Select what belongs in it.",
    gate: {
      kind: "multi",
      options: [
        { id: "issues", label: "The issues as framed, each marked with who carries the burden." },
        {
          id: "contradictions",
          label: "Where the two sides' versions contradict each other, each pinned to a page.",
        },
        { id: "relief", label: "The exact order you are asking the court to make today." },
        { id: "dates", label: "The dates that bite: next hearing, limitation, any interim order expiring." },
        { id: "everything", label: "Every fact on the file, in chronological order." },
        { id: "opinion", label: "Your view of who ought to win." },
      ],
      correct: ["issues", "contradictions", "relief", "dates"],
    },
    why:
      "A brief is a selection, and the two wrong answers both refuse to select. The full chronology is the file, not a brief — handing it over moves the work of choosing onto the person with the least time to do it. Your opinion on the outcome is not yours to give at this stage; what your senior needs is the material to form their own, which is why the contradictions must carry page pins. Everything in the four correct answers is something they may be asked about the moment the matter is called.",
    authority: "Practice, not statute — but the page pins are why the workspace records a source for every extracted fact.",
    hint: "Four belong. Ask of each: could your senior be asked about this in the first minute — and does it save them work, or move work onto them?",
  },
];

const STORAGE_KEY = "jl.training.v1";

export type Progress = { completed: string[] };

const EMPTY: Progress = { completed: [] };

function readProgress(): Progress {
  if (typeof window === "undefined") return EMPTY;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return EMPTY;
    const parsed = JSON.parse(raw) as Progress;
    const known = new Set(STEPS.map((step) => step.key));
    return { completed: (parsed.completed ?? []).filter((key) => known.has(key)) };
  } catch {
    return EMPTY;
  }
}

/**
 * Progress is browser state, so the component reads it through
 * `useSyncExternalStore` rather than an effect. The snapshot must be reference
 * stable between writes or React re-renders forever, hence the cache.
 */
let cached: Progress | null = null;
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((listener) => listener());
}

export function subscribeProgress(listener: () => void) {
  listeners.add(listener);
  // A student with the walkthrough open in two tabs sees one set of progress.
  const onStorage = (event: StorageEvent) => {
    if (event.key !== null && event.key !== STORAGE_KEY) return;
    cached = null;
    emit();
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", onStorage);
  };
}

export function getProgress(): Progress {
  if (!cached) cached = readProgress();
  return cached;
}

/** The server has no localStorage, so it always renders the zero state. */
export function getServerProgress(): Progress {
  return EMPTY;
}

export function setProgress(next: Progress) {
  cached = next;
  if (typeof window !== "undefined") {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      // A student in private browsing still gets the walkthrough, just not the memory of it.
    }
  }
  emit();
}

/** Set equality, order-insensitive — for `multi` gates. */
export function sameSet(a: string[], b: string[]) {
  if (a.length !== b.length) return false;
  const left = [...a].sort();
  const right = [...b].sort();
  return left.every((value, index) => value === right[index]);
}

/** Sequence equality — for `order` gates. */
export function sameOrder(a: string[], b: string[]) {
  return a.length === b.length && a.every((value, index) => value === b[index]);
}
