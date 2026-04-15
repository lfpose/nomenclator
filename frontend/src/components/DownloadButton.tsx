export interface DownloadButtonProps {
  jobId: string;
  status: string;
}

export function DownloadButton({ jobId, status }: DownloadButtonProps) {
  const isCompleted = status === "completed";

  if (!isCompleted) {
    return null;
  }

  return (
    <a
      href={`/jobs/${jobId}/download`}
      download
      className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
    >
      Download CSV
    </a>
  );
}
