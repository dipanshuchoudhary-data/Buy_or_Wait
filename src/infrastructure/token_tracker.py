from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock


@dataclass
class ModelUsage:
    provider: str
    model: str
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class TokenTracker:
    provider: str = "openrouter"
    usages: dict[str, ModelUsage] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock, repr=False)

    def record(
        self,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        calls: int = 1,
    ) -> None:
        with self._lock:
            usage = self.usages.setdefault(
                model, ModelUsage(provider=self.provider, model=model)
            )
            usage.calls += calls
            usage.input_tokens += max(0, input_tokens)
            usage.output_tokens += max(0, output_tokens)

    def totals(self) -> ModelUsage:
        combined = ModelUsage(provider=self.provider, model="all")
        for usage in self.usages.values():
            combined.calls += usage.calls
            combined.input_tokens += usage.input_tokens
            combined.output_tokens += usage.output_tokens
        return combined

    def reset(self) -> None:
        with self._lock:
            self.usages.clear()


tracker = TokenTracker()
