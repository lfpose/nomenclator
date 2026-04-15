/**
 * Submit button for committing a preview job to be processed
 * Calls /jobs/:id/commit and transitions form state to running
 */

import { useState } from "react";
import { Button } from "./ui/button";
import { Spinner } from "./Spinner";
import { jobsApi } from "../lib/jobs-api";

interface SubmitButtonProps {
  jobId: string;
  promptOverride?: string;
  taxonomy?: string;
  titlesPerRequest?: number;
  isDryRun: boolean;
  disabled?: boolean;
  onSubmit: (jobId: string) => void;
  onError: (message: string, details?: { code?: string; resetDate?: string }) => void;
}

export function SubmitButton({
  jobId,
  promptOverride,
  taxonomy,
  titlesPerRequest,
  isDryRun,
  disabled = false,
  onSubmit,
  onError,
}: SubmitButtonProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async () => {
    setIsSubmitting(true);
    try {
      const response = await jobsApi.commit(jobId, {
        prompt_override: promptOverride,
        taxonomy,
        titles_per_request: titlesPerRequest,
        is_dry_run: isDryRun,
      });

      // Transition to running state on 202
      onSubmit(response.job_id);
    } catch (err) {
      const error = err as { code?: string; message?: string; details?: { error?: { code?: string; reset_date?: string } } };

      if (error.code) {
        const errorData = error.details?.error;

        switch (errorData?.code) {
          case "spend_cap_exceeded":
            onError(
              error.message || "Monthly spend cap exceeded",
              { code: errorData.code, resetDate: errorData.reset_date }
            );
            break;
          case "job_already_running":
            onError(error.message || "Another job is already running", { code: errorData.code });
            break;
          default:
            onError(error.message || "Failed to submit job", { code: errorData?.code || error.code });
        }
      } else {
        onError("Failed to submit job. Please try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Button
      onClick={handleSubmit}
      disabled={disabled || isSubmitting}
      className="w-full sm:w-auto"
    >
      {isSubmitting ? (
        <>
          <Spinner className="mr-2 h-4 w-4" />
          Submitting...
        </>
      ) : (
        "Submit job"
      )}
    </Button>
  );
}
