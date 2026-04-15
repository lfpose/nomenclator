import { useState } from "react";
import { jobsApi, type ReviewResponse } from "@/lib/jobs-api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "./Spinner";

interface PromptReviewPanelProps {
  prompt: string;
  fewShots: string;
}

export function PromptReviewPanel({ prompt, fewShots }: PromptReviewPanelProps) {
  const [hasReviewed, setHasReviewed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [review, setReview] = useState<ReviewResponse | null>(null);

  const handleReview = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await jobsApi.reviewPrompt(prompt, fewShots);
      setReview(result);
      setHasReviewed(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to review prompt");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <Button
        variant="secondary"
        onClick={handleReview}
        disabled={loading}
      >
        {loading && <Spinner className="mr-2" />}
        {hasReviewed ? "Re-review" : "Review Prompt"}
      </Button>

      {error && (
        <div className="text-sm text-destructive">
          {error}
        </div>
      )}

      {review && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Badge variant={review.safe ? "default" : "destructive"}>
                {review.safe ? "Safe" : "Unsafe"}
              </Badge>
              <Badge variant="outline">
                {review.quality_score}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {review.summary && (
              <p className="text-sm">{review.summary}</p>
            )}

            {review.issues && review.issues.length > 0 && (
              <div>
                <h4 className="text-sm font-semibold mb-2">Issues</h4>
                <ul className="list-disc list-inside text-sm space-y-1">
                  {review.issues.map((issue, index) => (
                    <li key={index}>{issue}</li>
                  ))}
                </ul>
              </div>
            )}

            {review.suggestions && review.suggestions.length > 0 && (
              <div>
                <h4 className="text-sm font-semibold mb-2">Suggestions</h4>
                <ul className="list-disc list-inside text-sm space-y-1">
                  {review.suggestions.map((suggestion, index) => (
                    <li key={index}>{suggestion}</li>
                  ))}
                </ul>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
