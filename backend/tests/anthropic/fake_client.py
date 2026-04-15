from dataclasses import dataclass, field


@dataclass
class FakeBatch:
    id: str
    requests: list[dict]
    processing_status: str = "in_progress"
    result_rows: list[dict] = field(default_factory=list)


class FakeAnthropicBatchClient:
    def __init__(self) -> None:
        self.batches: dict[str, FakeBatch] = {}
        self._next_id = 0

    def submit_batch(self, requests: list[dict]) -> str:
        self._next_id += 1
        batch_id = f"batch_fake_{self._next_id}"
        self.batches[batch_id] = FakeBatch(id=batch_id, requests=requests)
        return batch_id

    def get_batch_status(self, batch_id: str) -> dict:
        b = self.batches[batch_id]
        return {"id": b.id, "processing_status": b.processing_status, "ended_at": None}

    def get_batch_results(self, batch_id: str) -> list[dict]:
        return self.batches[batch_id].result_rows

    def cancel_batch(self, batch_id: str) -> None:
        self.batches[batch_id].processing_status = "canceled"

    def complete_batch(self, batch_id: str, results: list[dict]) -> None:
        self.batches[batch_id].processing_status = "ended"
        self.batches[batch_id].result_rows = results
