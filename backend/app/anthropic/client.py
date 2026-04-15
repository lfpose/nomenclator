from typing import Protocol, runtime_checkable

from anthropic import Anthropic


@runtime_checkable
class AnthropicBatchClient(Protocol):
    def submit_batch(self, requests: list[dict]) -> str: ...

    def get_batch_status(self, batch_id: str) -> dict: ...

    def get_batch_results(self, batch_id: str) -> list[dict]: ...

    def cancel_batch(self, batch_id: str) -> None: ...


class RealAnthropicClient:
    def __init__(self, api_key: str):
        self._anthropic = Anthropic(api_key=api_key)

    def submit_batch(self, requests: list[dict]) -> str:
        batch = self._anthropic.messages.batches.create(requests=requests)
        return batch.id

    def get_batch_status(self, batch_id: str) -> dict:
        batch = self._anthropic.messages.batches.retrieve(batch_id)
        return {"id": batch.id, "processing_status": batch.processing_status, "ended_at": batch.ended_at}

    def get_batch_results(self, batch_id: str) -> list[dict]:
        return list(self._anthropic.messages.batches.results(batch_id))

    def cancel_batch(self, batch_id: str) -> None:
        self._anthropic.messages.batches.cancel(batch_id)
