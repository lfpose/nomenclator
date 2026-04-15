from tests.anthropic.fake_client import FakeAnthropicBatchClient


def test_fake_submit_returns_batch_id(fake_anthropic: FakeAnthropicBatchClient) -> None:
    """Verify that submit_batch returns a valid batch ID and stores the batch."""
    requests = [{"id": "t001", "title": "Jefe de Compras"}]
    batch_id = fake_anthropic.submit_batch(requests)

    assert batch_id is not None
    assert batch_id.startswith("batch_fake_")
    assert batch_id in fake_anthropic.batches
    assert fake_anthropic.batches[batch_id].requests == requests


def test_fake_complete_batch_sets_status_and_results(fake_anthropic: FakeAnthropicBatchClient) -> None:
    """Verify that complete_batch sets processing_status to 'ended' and stores results."""
    requests = [{"id": "t001", "title": "Jefe de Compras"}]
    batch_id = fake_anthropic.submit_batch(requests)
    results = [
        {
            "id": "t001",
            "male_es": "Jefe de Compras (M)",
            "female_es": "Jefa de Compras (F)",
            "category": "Procurement",
        }
    ]

    fake_anthropic.complete_batch(batch_id, results)

    assert fake_anthropic.batches[batch_id].processing_status == "ended"
    assert fake_anthropic.batches[batch_id].result_rows == results


def test_fake_cancel_sets_canceled_status(fake_anthropic: FakeAnthropicBatchClient) -> None:
    """Verify that cancel_batch sets processing_status to 'canceled'."""
    requests = [{"id": "t001", "title": "Jefe de Compras"}]
    batch_id = fake_anthropic.submit_batch(requests)

    fake_anthropic.cancel_batch(batch_id)

    assert fake_anthropic.batches[batch_id].processing_status == "canceled"
