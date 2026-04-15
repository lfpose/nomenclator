from app.anthropic.client import AnthropicBatchClient, RealAnthropicClient


class FakeAnthropicBatchClient:
    def __init__(self) -> None:
        self.batches: dict[str, dict] = {}
        self._next_id = 0

    def submit_batch(self, requests: list[dict]) -> str:
        self._next_id += 1
        batch_id = f"batch_fake_{self._next_id}"
        self.batches[batch_id] = {"id": batch_id, "processing_status": "in_progress", "requests": requests}
        return batch_id

    def get_batch_status(self, batch_id: str) -> dict:
        return self.batches[batch_id]

    def get_batch_results(self, batch_id: str) -> list[dict]:
        return [{"result": "mock"}]

    def cancel_batch(self, batch_id: str) -> None:
        if batch_id in self.batches:
            self.batches[batch_id]["processing_status"] = "canceled"


def test_protocol_accepts_fake_client() -> None:
    """Verify that Protocol structural typing works with a fake client."""
    fake: AnthropicBatchClient = FakeAnthropicBatchClient()
    batch_id = fake.submit_batch([{"test": "request"}])
    assert batch_id == "batch_fake_1"

    status = fake.get_batch_status(batch_id)
    assert status["id"] == batch_id
    assert status["processing_status"] == "in_progress"

    results = fake.get_batch_results(batch_id)
    assert isinstance(results, list)

    fake.cancel_batch(batch_id)
    status = fake.get_batch_status(batch_id)
    assert status["processing_status"] == "canceled"


def test_real_client_initializes_with_api_key() -> None:
    """Verify RealAnthropicClient can be instantiated without calling API."""
    client = RealAnthropicClient(api_key="test_key")
    assert client is not None
    assert isinstance(client, RealAnthropicClient)
    # Verify it implements the protocol (structural typing)
    assert isinstance(client, AnthropicBatchClient)


def test_fake_client_sanity_check() -> None:
    """Comprehensive sanity test of fake client operations."""
    fake = FakeAnthropicBatchClient()

    # Submit a batch
    requests = [{"test": "data1"}, {"test": "data2"}]
    batch_id = fake.submit_batch(requests)
    assert batch_id.startswith("batch_fake_")

    # Check status shape
    status = fake.get_batch_status(batch_id)
    assert isinstance(status, dict)
    assert "id" in status
    assert "processing_status" in status
    assert isinstance(status["id"], str)
    assert isinstance(status["processing_status"], str)

    # Check results shape
    results = fake.get_batch_results(batch_id)
    assert isinstance(results, list)
    assert all(isinstance(r, dict) for r in results)

    # Cancel batch
    fake.cancel_batch(batch_id)
    status = fake.get_batch_status(batch_id)
    assert status["processing_status"] == "canceled"
