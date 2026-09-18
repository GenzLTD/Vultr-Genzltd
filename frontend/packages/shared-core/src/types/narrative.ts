/**
 * Narrative types — Phase 0 feedback collection.
 * Ownership: Jason
 *
 * Tracks narrative sessions, events, and convergence-point
 * qualitative feedback for the Phase 0 Navigator text adventure.
 */

/** Valid narrative domains (六域 + 迷雾域) */
export type NarrativeDomain =
  | "职业域"
  | "诗域"
  | "自我域"
  | "身份域"
  | "信任域"
  | "迷雾域"
  | "career"
  | "poetry"
  | "self"
  | "identity"
  | "trust"
  | "unknown";

/** Event types logged during a narrative session */
export type NarrativeEventType =
  | "domain_enter"
  | "choice_made"
  | "convergence_reached"
  | "share_attempt"
  | "replay";

/** POST /v1/narrative/start request */
export interface NarrativeStartRequest {
  domain: NarrativeDomain;
}

/** POST /v1/narrative/start response */
export interface NarrativeStartResponse {
  session_id: string;
  domain: string;
}

/** POST /v1/narrative/event request */
export interface NarrativeEventRequest {
  session_id: string;
  event_type: NarrativeEventType;
  domain?: string;
  choice?: string;
  navigator_line?: string;
  metadata?: Record<string, unknown>;
}

/** POST /v1/narrative/end request */
export interface NarrativeEndRequest {
  session_id: string;
  completed: boolean;
  duration_seconds: number;
}

/** POST /v1/narrative/feedback request */
export interface NarrativeFeedbackRequest {
  session_id: string;
  /** Did Navigator touch you? (required) */
  resonated: boolean;
  /** A Navigator line the user can recall (optional) */
  navigator_quote?: string;
  /** 0=no, 1=maybe, 2=yes */
  would_replay?: number;
  /** Did the user share? */
  shared?: boolean;
  /** Where did they share? */
  share_channel?: "wechat" | "moments" | "link" | "other";
  /** Free-text qualitative feedback */
  open_feedback?: string;
}

/** GET /v1/narrative/stats response */
export interface NarrativeStats {
  total_sessions: number;
  completed_sessions: number;
  completion_rate: number;
  feedback_count: number;
  resonance_rate: number;
  share_rate: number;
  replay_intent_rate: number;
  top_quotes: Array<{ quote: string; count: number }>;
  domains: Array<{ domain: string; count: number }>;
  open_feedback: Array<{ domain: string; text: string; at: string }>;
}

// ============================================================
// Act 1 State Machine types (GDD §5.1)
// ============================================================

/** Act 1 domain content summary (from /engine/act1/content) */
export interface Act1DomainSummary {
  icon: string;
  en: string;
  color: string;
  emotion_arc: string;
  encounter_summary: string;
  choice_count: number;
}

/** Act 1 step definition */
export interface Act1Step {
  id: number;
  label: string;
  desc: string;
}

/** Convergence texture for a single domain */
export interface ConvergenceTexture {
  domain: string;
  icon: string;
  color: string;
  interpretation: string;
  emotion: string;
  inner_thought: string;
  truth_distance: "near" | "mid" | "far";
}

/** Act 1 content library response */
export interface Act1ContentResponse {
  domains: Record<string, Act1DomainSummary>;
  steps: Act1Step[];
  navigator_lines: Record<string, { line: string; confidence: number }>;
  convergence_comparison: ConvergenceTexture[];
  verdict: string;
}

/** Act 1 choice option */
export interface Act1ChoiceOption {
  index: number;
  label: string;
}

/** Act 1 session state */
export interface Act1SessionState {
  session_id: string;
  user_id: string;
  domain: string;
  domain_info: {
    name: string;
    icon: string;
    color: string;
    emotion_arc: string;
  } | null;
  step: number;
  step_label: string;
  step_desc: string;
  chosen_option: number | null;
  completed: boolean;
  remaining_steps: number;
  /** Whether the chosen domain supports a cross-domain path (e.g. 职业域→诗域) */
  has_cross_domain?: boolean;
}

/** Act 1 advance response */
export interface Act1AdvanceResponse {
  step: number;
  label: string;
  desc: string;
  domain: string;
  narrative: string | null;
  navigator_line: string | null;
  navigator_confidence: number | null;
  choices: Act1ChoiceOption[] | null;
  choice_index: number | null;
  completed: boolean;
  domain_emotion?: string;
  imprint_name?: string;
  convergence_texture?: ConvergenceTexture;
  end_hook?: string;
  prev_step?: number;
  /** Cross-domain echo triggered (职业域→诗域) */
  echo_triggered?: boolean;
  /** Whether a cross-domain choice was made */
  cross_chosen?: boolean;
  error?: string;
}

/** Act 1 choice request */
export interface Act1ChoiceRequest {
  session_id: string;
  choice_index: number;
}

/** Act 1 choice response */
export interface Act1ChoiceResponse {
  step: number;
  chosen_option: number;
  imprint_name: string;
  imprint_axis: string;
  imprint_points: number;
  consequence: string | null;
  error?: string;
}

/** Act 1 init request */
export interface Act1InitRequest {
  session_id: string;
  domain: NarrativeDomain;
}
