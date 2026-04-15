from unittest.mock import Mock, patch

import pytest

from app.anthropic.review import PromptReview, review_prompt, REVIEW_SYSTEM_PROMPT, REVIEW_TOOL


def test_review_prompt_returns_prompt_review_dataclass():
    """Test that review_prompt returns a PromptReview dataclass."""
    mock_tool_use = Mock()
    mock_tool_use.type = "tool_use"
    mock_tool_use.input = {
        "safe": True,
        "quality_score": "good",
        "issues": [],
        "suggestions": [],
        "summary": "Prompt is well-structured.",
    }

    mock_message = Mock()
    mock_message.content = [mock_tool_use]

    mock_client = Mock()
    mock_client.messages.create.return_value = mock_message

    with patch("app.anthropic.review.Anthropic", return_value=mock_client):
        result = review_prompt("test-key", "test prompt", "[]")

    assert isinstance(result, PromptReview)
    assert result.safe is True
    assert result.quality_score == "good"
    assert result.issues == []
    assert result.suggestions == []
    assert result.summary == "Prompt is well-structured."


def test_review_prompt_calls_haiku_with_tool_choice():
    """Test that review_prompt calls claude-haiku-4-5 with forced tool_choice."""
    mock_tool_use = Mock()
    mock_tool_use.type = "tool_use"
    mock_tool_use.input = {
        "safe": True,
        "quality_score": "good",
        "issues": [],
        "suggestions": [],
        "summary": "Good prompt.",
    }

    mock_message = Mock()
    mock_message.content = [mock_tool_use]

    mock_client = Mock()
    mock_client.messages.create.return_value = mock_message

    with patch("app.anthropic.review.Anthropic", return_value=mock_client):
        review_prompt("test-key", "test prompt", "[]")

    mock_client.messages.create.assert_called_once()
    call_args = mock_client.messages.create.call_args
    assert call_args.kwargs["model"] == "claude-haiku-4-5"
    assert call_args.kwargs["max_tokens"] == 1000
    assert call_args.kwargs["temperature"] == 0
    assert call_args.kwargs["system"] == REVIEW_SYSTEM_PROMPT
    assert call_args.kwargs["tools"] == [REVIEW_TOOL]
    assert call_args.kwargs["tool_choice"] == {"type": "tool", "name": "review_prompt"}


def test_review_prompt_handles_good_quality_score():
    """Test that review_prompt correctly parses a good quality_score."""
    mock_tool_use = Mock()
    mock_tool_use.type = "tool_use"
    mock_tool_use.input = {
        "safe": True,
        "quality_score": "good",
        "issues": [],
        "suggestions": ["Consider adding more examples."],
        "summary": "Strong prompt with minor suggestions.",
    }

    mock_message = Mock()
    mock_message.content = [mock_tool_use]

    mock_client = Mock()
    mock_client.messages.create.return_value = mock_message

    with patch("app.anthropic.review.Anthropic", return_value=mock_client):
        result = review_prompt("test-key", "test prompt", "[]")

    assert result.safe is True
    assert result.quality_score == "good"
    assert result.issues == []
    assert result.suggestions == ["Consider adding more examples."]
    assert result.summary == "Strong prompt with minor suggestions."


def test_review_prompt_handles_poor_quality_score():
    """Test that review_prompt correctly parses a poor quality_score with issues."""
    mock_tool_use = Mock()
    mock_tool_use.type = "tool_use"
    mock_tool_use.input = {
        "safe": True,
        "quality_score": "poor",
        "issues": [
            "Prompt is unclear about output format.",
            "Missing instructions for English→Spanish translation.",
        ],
        "suggestions": [
            "Add clear output format specification.",
            "Include examples of English→Spanish mapping.",
        ],
        "summary": "Prompt needs significant improvements.",
    }

    mock_message = Mock()
    mock_message.content = [mock_tool_use]

    mock_client = Mock()
    mock_client.messages.create.return_value = mock_message

    with patch("app.anthropic.review.Anthropic", return_value=mock_client):
        result = review_prompt("test-key", "test prompt", "[]")

    assert result.safe is True
    assert result.quality_score == "poor"
    assert len(result.issues) == 2
    assert "Prompt is unclear about output format." in result.issues
    assert "Missing instructions for English→Spanish translation." in result.issues
    assert len(result.suggestions) == 2
    assert result.summary == "Prompt needs significant improvements."


def test_review_prompt_raises_on_api_error():
    """Test that review_prompt propagates API errors."""
    mock_client = Mock()
    mock_client.messages.create.side_effect = Exception("API error: unauthorized")

    with patch("app.anthropic.review.Anthropic", return_value=mock_client):
        with pytest.raises(Exception, match="API error: unauthorized"):
            review_prompt("test-key", "test prompt", "[]")
