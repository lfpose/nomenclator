import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Check, Copy } from "lucide-react";
import { APIError } from "@/lib/api";

export interface ErrorDetails {
  /** Short summary shown as the title. */
  title?: string;
  /** Optional context — e.g. "while previewing", "while submitting". */
  context?: string;
  /** The actual error. Either an APIError, a generic Error, or already-stringified. */
  error: unknown;
}

interface ErrorModalProps {
  open: boolean;
  onClose: () => void;
  details: ErrorDetails | null;
}

function buildClipboardText(d: ErrorDetails): string {
  const parts: string[] = [];
  if (d.title) parts.push(`# ${d.title}`);
  if (d.context) parts.push(`context: ${d.context}`);
  const e = d.error;
  if (e instanceof APIError) {
    parts.push(`code:    ${e.code}`);
    parts.push(`status:  ${e.status}`);
    parts.push(`message: ${e.message}`);
    if (e.details) {
      parts.push("details:");
      parts.push(JSON.stringify(e.details, null, 2));
    }
  } else if (e instanceof Error) {
    parts.push(`name:    ${e.name}`);
    parts.push(`message: ${e.message}`);
    if (e.stack) {
      parts.push("stack:");
      parts.push(e.stack);
    }
  } else {
    parts.push("error:");
    parts.push(typeof e === "string" ? e : JSON.stringify(e, null, 2));
  }
  parts.push(`at: ${new Date().toISOString()}`);
  parts.push(`url: ${typeof window !== "undefined" ? window.location.href : ""}`);
  parts.push(`ua: ${typeof navigator !== "undefined" ? navigator.userAgent : ""}`);
  return parts.join("\n");
}

export function ErrorModal({ open, onClose, details }: ErrorModalProps) {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!open) setCopied(false);
  }, [open]);

  if (!details) return null;

  const e = details.error;
  const isApi = e instanceof APIError;
  const apiErr = isApi ? (e as APIError) : null;
  const apiDetails = (apiErr?.details ?? null) as Record<string, unknown> | null;

  // Backend dev mode propagates the real exception inside details — use it as the
  // primary message so the user doesn't just see "An unexpected error occurred."
  const exceptionType =
    (apiDetails?.exception_type as string | undefined) || null;
  const exceptionMessage =
    (apiDetails?.exception_message as string | undefined) || null;
  const traceback = (apiDetails?.traceback as string | undefined) || null;

  const headline =
    details.title ||
    (apiErr ? `${apiErr.code} (HTTP ${apiErr.status})` : "Error");

  const primaryMessage =
    exceptionMessage ||
    (apiErr
      ? apiErr.message
      : e instanceof Error
      ? e.message
      : String(e));

  const detailsJson = apiErr
    ? apiErr.details
    : e instanceof Error
    ? { name: e.name, stack: e.stack }
    : { value: e };

  const fullText = buildClipboardText(details);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(fullText);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Fallback: select + copy via textarea
      const ta = document.createElement("textarea");
      ta.value = fullText;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent
        className="sm:max-w-2xl"
        data-testid="error-modal"
      >
        <DialogHeader>
          <DialogTitle className="text-destructive">{headline}</DialogTitle>
          {details.context && (
            <div className="text-xs text-muted-foreground">{details.context}</div>
          )}
        </DialogHeader>

        <div className="space-y-3">
          <div>
            <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-1">
              {exceptionType ? `Server exception · ${exceptionType}` : "Message"}
            </div>
            <div
              data-testid="error-message"
              className="text-sm font-mono bg-muted/50 rounded-md p-3 break-words whitespace-pre-wrap"
            >
              {primaryMessage}
            </div>
          </div>

          {traceback && (
            <details>
              <summary className="text-xs font-medium uppercase tracking-wide text-muted-foreground cursor-pointer hover:text-foreground">
                Traceback
              </summary>
              <pre
                data-testid="error-traceback"
                className="mt-1 text-xs font-mono bg-muted/50 rounded-md p-3 max-h-48 overflow-auto"
              >
                {traceback}
              </pre>
            </details>
          )}

          {detailsJson != null && typeof detailsJson === "object" && Object.keys(detailsJson).length > 0 && (
            <details>
              <summary className="text-xs font-medium uppercase tracking-wide text-muted-foreground cursor-pointer hover:text-foreground">
                Raw details
              </summary>
              <pre
                data-testid="error-details"
                className="mt-1 text-xs font-mono bg-muted/50 rounded-md p-3 max-h-48 overflow-auto"
              >
                {JSON.stringify(detailsJson, null, 2)}
              </pre>
            </details>
          )}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={handleCopy}
            data-testid="btn-copy-error"
            className="gap-2"
          >
            {copied ? (
              <>
                <Check className="h-4 w-4" />
                Copied
              </>
            ) : (
              <>
                <Copy className="h-4 w-4" />
                Copy error
              </>
            )}
          </Button>
          <Button onClick={onClose} data-testid="btn-close-error">
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
