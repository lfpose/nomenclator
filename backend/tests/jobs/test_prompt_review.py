"""Tests for prompt review service in jobs/service.py."""

from unittest.mock import patch

from app.anthropic.review import PromptReview
from app.jobs.service import APIError, review_operator_prompt


def test_review_returns_prompt_review_object():
    """Test that review_operator_prompt returns a PromptReview object."""
    api_key = "test-key"
    prompt = "Normalize these job titles"
    few_shots = '[{"input": "CEO", "male_es": "Director General", "female_es": "Directora General", "category": "Management"}]'

    # Mock the review_prompt function to return a PromptReview
    expected = PromptReview(
        safe=True,
        quality_score="good",
        issues=[],
        suggestions=[],
        summary="The prompt is clear and comprehensive.",
    )

    with patch("app.anthropic.review.review_prompt", return_value=expected) as mock_review:
        result = review_operator_prompt(api_key, prompt, few_shots)

        # Verify the function was called with correct arguments
        mock_review.assert_called_once_with(api_key, prompt, few_shots)

        # Verify the result is a PromptReview object
        assert isinstance(result, PromptReview)
        assert result.safe is True
        assert result.quality_score == "good"
        assert result.issues == []
        assert result.suggestions == []
        assert result.summary == "The prompt is clear and comprehensive."


def test_review_propagates_api_errors_as_api_error():
    """Test that API errors from review_prompt are converted to APIError."""
    api_key = "test-key"
    prompt = "Normalize these job titles"
    few_shots = '[{"input": "CEO", "male_es": "Director General", "female_es": "Directora General", "category": "Management"}]'

    # Mock the review_prompt function to raise an exception
    original_error = Exception("Invalid API key")

    with patch("app.anthropic.review.review_prompt", side_effect=original_error):
        # Verify that APIError is raised
        try:
            review_operator_prompt(api_key, prompt, few_shots)
            assert False, "Expected APIError to be raised"
        except APIError as e:
            # Verify error code and message
            assert e.code == "prompt_review_failed"
            assert "Failed to review prompt:" in e.message
            assert "Invalid API key" in e.message

            # Verify the original exception is chained
            assert e.__cause__ is original_error
