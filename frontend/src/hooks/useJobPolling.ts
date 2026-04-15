import { useEffect, useState } from "react";
import { jobsApi, type JobDetail } from "@/lib/jobs-api";

const POLL_INTERVAL = 5000; // 5 seconds

export function useJobPolling(jobId: string, enabled: boolean = true) {
  const [job, setJob] = useState<JobDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled || !jobId) {
      return;
    }

    let isPolling = true;

    const poll = async () => {
      try {
        const response = await jobsApi.get(jobId);
        if (!isPolling) return;

        setJob(response);
        setError(null);

        // Stop polling if terminal status
        const terminalStatuses = ["completed", "failed", "cancelled"];
        if (terminalStatuses.includes(response.status)) {
          isPolling = false;
          return;
        }
      } catch (err) {
        if (!isPolling) return;
        setError(err instanceof Error ? err.message : "Failed to fetch job status");
        isPolling = false;
      }
    };

    // Initial poll
    poll();

    // Set up interval for subsequent polls
    const intervalId = setInterval(() => {
      if (isPolling) {
        poll();
      } else {
        clearInterval(intervalId);
      }
    }, POLL_INTERVAL);

    return () => {
      isPolling = false;
      clearInterval(intervalId);
    };
  }, [jobId, enabled]);

  return { job, error };
}
