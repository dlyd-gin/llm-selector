"""In-memory failure tracking store with cooldown logic."""

from datetime import datetime, timedelta
from typing import Dict, List

from .models import FailureRecord


class MemoryStore:
    """Tracks provider failures with cooldown periods.

    The store maintains failure records for providers and implements a 60-second
    cooldown before a provider can be considered available again.
    """

    def __init__(self):
        """Initialize an empty memory store."""
        self._store: Dict[str, FailureRecord] = {}

    def record_failure(self, model_id: str, status_code: int) -> None:
        """Record a provider failure.

        Only updates the recorded_at timestamp if more than 60 seconds have
        passed since the last failure record.

        Args:
            model_id: Unique identifier of the failed provider
            status_code: HTTP status code of the failure
        """
        now = datetime.now()

        if model_id in self._store:
            # Only update if more than 60 seconds have passed
            last_recorded = self._store[model_id].recorded_at
            if (now - last_recorded).total_seconds() > 60:
                self._store[model_id] = FailureRecord(
                    model_id=model_id,
                    status_code=status_code,
                    recorded_at=now
                )
        else:
            # First failure for this provider
            self._store[model_id] = FailureRecord(
                model_id=model_id,
                status_code=status_code,
                recorded_at=now
            )

    def is_available(self, model_id: str, cooldown_seconds: int = 60) -> bool:
        """Check if a provider is available (passed cooldown period).

        Args:
            model_id: Unique identifier of the provider
            cooldown_seconds: Cooldown period in seconds (default: 60)

        Returns:
            True if provider is available, False if still in cooldown
        """
        if model_id not in self._store:
            return True

        record = self._store[model_id]
        elapsed = (datetime.now() - record.recorded_at).total_seconds()
        return elapsed >= cooldown_seconds

    def get_unavailable_providers(
        self,
        model_name: str,
        model_mappings: dict,
        cooldown_seconds: int = 60
    ) -> List[str]:
        """Get list of unavailable provider IDs for a model.

        Args:
            model_name: Name of the model (e.g., "gpt-4.1")
            model_mappings: Dictionary of model mappings
            cooldown_seconds: Cooldown period in seconds (default: 60)

        Returns:
            List of model_ids that are currently unavailable
        """
        if model_name not in model_mappings:
            return []

        providers = model_mappings[model_name]
        unavailable = []

        for provider in providers:
            model_id = provider["model_id"]
            if not self.is_available(model_id, cooldown_seconds):
                unavailable.append(model_id)

        return unavailable

    def calculate_shortest_wait(
        self,
        model_name: str,
        model_mappings: dict,
        cooldown_seconds: int = 60
    ) -> int:
        """Calculate seconds until the next provider becomes available.

        Args:
            model_name: Name of the model (e.g., "gpt-4.1")
            model_mappings: Dictionary of model mappings
            cooldown_seconds: Cooldown period in seconds (default: 60)

        Returns:
            Seconds until next provider available, or 0 if none in cooldown
        """
        if model_name not in model_mappings:
            return 0

        providers = model_mappings[model_name]
        shortest_wait = float('inf')

        for provider in providers:
            model_id = provider["model_id"]
            if model_id in self._store:
                record = self._store[model_id]
                elapsed = (datetime.now() - record.recorded_at).total_seconds()
                remaining = max(0, cooldown_seconds - elapsed)

                if remaining > 0 and remaining < shortest_wait:
                    shortest_wait = remaining

        return int(shortest_wait) if shortest_wait != float('inf') else 0

    def get_all_records(self) -> Dict[str, FailureRecord]:
        """Get all failure records for inspection.

        Returns:
            Dictionary mapping model_id to FailureRecord
        """
        return self._store.copy()

    def reset(self) -> None:
        """Clear all failure records."""
        self._store.clear()
