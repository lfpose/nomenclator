/**
 * Custom hook for Tool page form state machine
 * Manages the entire Tool page's state with useReducer
 */

import { useReducer } from "react";
import type { PreviewResponse, JobDetail } from "../lib/jobs-api";

export type ToolState =
  | { kind: "idle" }
  | { kind: "input_loaded"; input: { file?: File; text?: string } }
  | { kind: "previewing" }
  | { kind: "previewed"; preview: PreviewResponse }
  | { kind: "reclustering"; preview: PreviewResponse }
  | { kind: "reviewing_prompt" }
  | { kind: "submitting" }
  | { kind: "running"; jobId: string }
  | { kind: "completed"; jobId: string; job: JobDetail }
  | { kind: "failed"; jobId: string; message: string }
  | { kind: "cancelled"; jobId: string };

type ToolAction =
  | { type: "LOAD_INPUT"; payload: { file?: File; text?: string } }
  | { type: "START_PREVIEW" }
  | { type: "PREVIEW_SUCCESS"; payload: PreviewResponse }
  | { type: "START_RECLUSTER" }
  | { type: "RECLUSTER_SUCCESS"; payload: PreviewResponse }
  | { type: "START_REVIEW_PROMPT" }
  | { type: "REVIEW_PROMPT_SUCCESS" }
  | { type: "START_COMMIT" }
  | { type: "COMMIT_SUCCESS"; payload: { jobId: string } }
  | { type: "POLL_UPDATE"; payload: JobDetail }
  | { type: "POLL_FAILED"; payload: { jobId: string; message: string } }
  | { type: "POLL_CANCELLED"; payload: string }
  | { type: "RESET" };

interface FormState {
  row_subset_mode: "all" | "first_n" | "random_n";
  row_subset_n: number | null;
  is_dry_run: boolean;
}

interface ToolFormState extends FormState {
  toolState: ToolState;
}

const INITIAL_FORM_STATE: FormState = {
  row_subset_mode: "all",
  row_subset_n: null,
  is_dry_run: false,
};

const INITIAL_STATE: ToolFormState = {
  toolState: { kind: "idle" },
  ...INITIAL_FORM_STATE,
};

function toolReducer(state: ToolFormState, action: ToolAction): ToolFormState {
  switch (action.type) {
    case "LOAD_INPUT":
      return {
        ...state,
        toolState: { kind: "input_loaded", input: action.payload },
      };

    case "START_PREVIEW":
      return {
        ...state,
        toolState: { kind: "previewing" },
      };

    case "PREVIEW_SUCCESS":
      return {
        ...state,
        toolState: { kind: "previewed", preview: action.payload },
      };

    case "START_RECLUSTER":
      if (state.toolState.kind === "previewed") {
        return {
          ...state,
          toolState: { kind: "reclustering", preview: state.toolState.preview },
        };
      }
      return state;

    case "RECLUSTER_SUCCESS":
      return {
        ...state,
        toolState: { kind: "previewed", preview: action.payload },
      };

    case "START_REVIEW_PROMPT":
      return {
        ...state,
        toolState: { kind: "reviewing_prompt" },
      };

    case "REVIEW_PROMPT_SUCCESS":
      // Return to previous state after review
      return state;

    case "START_COMMIT":
      return {
        ...state,
        toolState: { kind: "submitting" },
      };

    case "COMMIT_SUCCESS":
      return {
        ...state,
        toolState: { kind: "running", jobId: action.payload.jobId },
      };

    case "POLL_UPDATE":
      if (state.toolState.kind === "running") {
        const job = action.payload;
        if (job.status === "completed") {
          return {
            ...state,
            toolState: { kind: "completed", jobId: state.toolState.jobId, job },
          };
        }
        // Still running, keep same state
        return state;
      }
      return state;

    case "POLL_FAILED":
      if (state.toolState.kind === "running") {
        return {
          ...state,
          toolState: { kind: "failed", jobId: state.toolState.jobId, message: action.payload.message },
        };
      }
      return state;

    case "POLL_CANCELLED":
      return {
        ...state,
        toolState: { kind: "cancelled", jobId: action.payload },
      };

    case "RESET":
      return {
        ...INITIAL_FORM_STATE,
        toolState: { kind: "idle" },
      };

    default:
      return state;
  }
}

export function useToolForm() {
  const [state, dispatch] = useReducer(toolReducer, INITIAL_STATE);

  const loadInput = (input: { file?: File; text?: string }) => {
    dispatch({ type: "LOAD_INPUT", payload: input });
  };

  const startPreview = () => {
    dispatch({ type: "START_PREVIEW" });
  };

  const previewSuccess = (preview: PreviewResponse) => {
    dispatch({ type: "PREVIEW_SUCCESS", payload: preview });
  };

  const startRecluster = () => {
    dispatch({ type: "START_RECLUSTER" });
  };

  const reclusterSuccess = (preview: PreviewResponse) => {
    dispatch({ type: "RECLUSTER_SUCCESS", payload: preview });
  };

  const startReviewPrompt = () => {
    dispatch({ type: "START_REVIEW_PROMPT" });
  };

  const reviewPromptSuccess = () => {
    dispatch({ type: "REVIEW_PROMPT_SUCCESS" });
  };

  const startCommit = () => {
    dispatch({ type: "START_COMMIT" });
  };

  const commitSuccess = (jobId: string) => {
    dispatch({ type: "COMMIT_SUCCESS", payload: { jobId } });
  };

  const pollUpdate = (job: JobDetail) => {
    dispatch({ type: "POLL_UPDATE", payload: job });
  };

  const pollFailed = (jobId: string, message: string) => {
    dispatch({ type: "POLL_FAILED", payload: { jobId, message } });
  };

  const pollCancelled = (jobId: string) => {
    dispatch({ type: "POLL_CANCELLED", payload: jobId });
  };

  const reset = () => {
    dispatch({ type: "RESET" });
  };

  const setRowSubsetMode = (mode: "all" | "first_n" | "random_n") => {
    return {
      ...state,
      row_subset_mode: mode,
      row_subset_n: mode === "all" ? null : state.row_subset_n,
    };
  };

  const setRowSubsetN = (n: number | null) => {
    return {
      ...state,
      row_subset_n: n,
    };
  };

  const setDryRun = (isDryRun: boolean) => {
    return {
      ...state,
      is_dry_run: isDryRun,
    };
  };

  return {
    state,
    loadInput,
    startPreview,
    previewSuccess,
    startRecluster,
    reclusterSuccess,
    startReviewPrompt,
    reviewPromptSuccess,
    startCommit,
    commitSuccess,
    pollUpdate,
    pollFailed,
    pollCancelled,
    reset,
    setRowSubsetMode,
    setRowSubsetN,
    setDryRun,
  };
}
