import { Check, Loader2 } from "lucide-react";
import type { ToolState } from "@/hooks/useToolForm";

type StepStatus = "todo" | "active" | "done" | "loading" | "error";

interface Step {
  id: string;
  label: string;
  status: StepStatus;
}

function statusFor(toolState: ToolState): Step[] {
  const k = toolState.kind;

  const inputDone =
    k !== "idle" ||
    // input_loaded and beyond all count input as done
    false;
  const inputStatus: StepStatus =
    k === "idle" ? "active" : inputDone || k !== "idle" ? "done" : "todo";

  const previewActive = k === "input_loaded";
  const previewLoading = k === "previewing" || k === "reclustering";
  const previewDone =
    k === "previewed" ||
    k === "submitting" ||
    k === "running" ||
    k === "completed" ||
    k === "failed" ||
    k === "cancelled";
  const previewStatus: StepStatus = previewLoading
    ? "loading"
    : previewDone
    ? "done"
    : previewActive
    ? "active"
    : "todo";

  const submitActive = k === "previewed";
  const submitLoading = k === "submitting";
  const submitDone =
    k === "running" || k === "completed" || k === "failed" || k === "cancelled";
  const submitStatus: StepStatus = submitLoading
    ? "loading"
    : submitDone
    ? "done"
    : submitActive
    ? "active"
    : "todo";

  const runLoading = k === "running";
  const runDone = k === "completed";
  const runError = k === "failed" || k === "cancelled";
  const runStatus: StepStatus = runLoading
    ? "loading"
    : runDone
    ? "done"
    : runError
    ? "error"
    : k === "submitting"
    ? "active"
    : "todo";

  return [
    { id: "input", label: "Input", status: inputStatus },
    { id: "preview", label: "Preview", status: previewStatus },
    { id: "submit", label: "Submit", status: submitStatus },
    { id: "run", label: "Run", status: runStatus },
  ];
}

function dot(status: StepStatus, idx: number) {
  const base =
    "flex h-6 w-6 items-center justify-center rounded-full text-xs font-medium tabular-nums";
  if (status === "done")
    return (
      <div className={`${base} bg-foreground text-background`}>
        <Check className="h-3.5 w-3.5" />
      </div>
    );
  if (status === "loading")
    return (
      <div className={`${base} bg-foreground/10 text-foreground`}>
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
      </div>
    );
  if (status === "error")
    return <div className={`${base} bg-destructive text-destructive-foreground`}>!</div>;
  if (status === "active")
    return <div className={`${base} bg-foreground text-background`}>{idx}</div>;
  return (
    <div className={`${base} border border-muted-foreground/30 text-muted-foreground`}>
      {idx}
    </div>
  );
}

export function StepIndicator({ toolState }: { toolState: ToolState }) {
  const steps = statusFor(toolState);

  return (
    <div
      data-testid="step-indicator"
      className="flex items-center gap-2 px-4 py-2 border-b bg-background/50 flex-shrink-0"
    >
      {steps.map((s, i) => (
        <div key={s.id} className="flex items-center gap-2">
          {dot(s.status, i + 1)}
          <span
            className={`text-sm ${
              s.status === "active" || s.status === "loading"
                ? "font-medium"
                : s.status === "todo"
                ? "text-muted-foreground"
                : ""
            }`}
            data-testid={`step-${s.id}`}
            data-status={s.status}
          >
            {s.label}
          </span>
          {i < steps.length - 1 && (
            <div className="h-px w-6 bg-muted-foreground/30 mx-1" />
          )}
        </div>
      ))}
    </div>
  );
}
