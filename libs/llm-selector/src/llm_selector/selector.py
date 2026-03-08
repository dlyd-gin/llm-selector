"""Main provider selector with retry logic."""

import os
import random
import traceback
from typing import Dict, Optional

from dotenv import load_dotenv

from .config import MODEL_MAPPINGS
from .memory_store import MemoryStore


class LLMSelector:
    """Intelligently select providers with automatic retry and cooldown tracking.

    This class manages provider selection across multiple LLM providers,
    tracking failures and implementing cooldown periods to avoid hammering
    recently failed providers.
    """

    def __init__(self, dotenv_path: str = ".env", as_equal_as_possible: bool = False):
        """Initialize the provider selector.

        Args:
            dotenv_path: Path to .env file for environment variables
            as_equal_as_possible: If True, use round-robin selection for equal distribution.
                                 If False (default), use random selection.
        """
        # Load environment variables
        load_dotenv(dotenv_path)

        # Pre-resolve all provider configurations
        self.resolved_mappings = self._create_resolved_mappings()

        # Initialize memory store for failure tracking
        self.memory_store = MemoryStore()

        # Track last suggested provider for each model
        self.last_suggested: Dict[str, str] = {}

        # Flag for equal distribution
        self.as_equal_as_possible = as_equal_as_possible

        # Round-robin tracking: maps model_name -> last used provider_id
        self.round_robin_last_used: Dict[str, str] = {}

    def _resolve_env_vars(self, provider_config: dict) -> dict:
        """Resolve environment variable references in provider config.

        Args:
            provider_config: Provider configuration dictionary

        Returns:
            Provider config with resolved environment variables
        """
        resolved = provider_config.copy()

        # Resolve api_key if it references an environment variable
        if "api_key" in resolved and resolved["api_key"]:
            env_var_name = resolved["api_key"]
            if env_var_name == "DUMMY_KEY":
                resolved["api_key"] = "DUMMY_KEY"
            # Check if it looks like an env var (all uppercase with underscores)
            elif env_var_name.isupper() and "_" in env_var_name:
                env_value = os.environ.get(env_var_name)
                if env_value:
                    resolved["api_key"] = env_value
                else:
                    # Keep the env var name but log warning
                    print(f"Warning: Environment variable {env_var_name} not found")

        # Resolve api_base if it references an environment variable
        if "api_base" in resolved and resolved["api_base"]:
            env_var_name = resolved["api_base"]
            if env_var_name.isupper() and "_" in env_var_name:
                env_value = os.environ.get(env_var_name)
                if env_value:
                    resolved["api_base"] = env_value
                else:
                    print(f"Warning: Environment variable {env_var_name} not found")

        return resolved

    def _create_resolved_mappings(self) -> dict:
        """Create a resolved copy of MODEL_MAPPINGS with env vars resolved.

        Returns:
            Dictionary with same structure as MODEL_MAPPINGS but with resolved env vars
        """
        resolved = {}
        for model_name, providers in MODEL_MAPPINGS.items():
            resolved[model_name] = [
                self._resolve_env_vars(provider)
                for provider in providers
            ]
        return resolved

    def _select_provider(self, model_name: str, available_providers: list) -> dict:
        """Select a provider from available providers based on selection strategy.

        Args:
            model_name: Name of the model for round-robin tracking
            available_providers: List of available provider configs

        Returns:
            Selected provider config
        """
        if not self.as_equal_as_possible:
            # Default: random selection
            return random.choice(available_providers)

        # Round-robin selection based on provider ID tracking

        # Get full provider list for this model to maintain consistent ordering
        all_providers = self.resolved_mappings[model_name]

        # If this is the first selection for this model, start with first available
        if model_name not in self.round_robin_last_used:
            selected = available_providers[0]
            self.round_robin_last_used[model_name] = selected["model_id"]
            return selected

        # Find the last used provider in the full list
        last_used_id = self.round_robin_last_used[model_name]

        # Find position of last used provider in full list
        last_position = None
        for i, provider in enumerate(all_providers):
            if provider["model_id"] == last_used_id:
                last_position = i
                break

        # If last used provider not found (shouldn't happen), start from beginning
        if last_position is None:
            selected = available_providers[0]
            self.round_robin_last_used[model_name] = selected["model_id"]
            return selected

        # Create a set of available provider IDs for O(1) lookup
        available_ids = {p["model_id"] for p in available_providers}

        # Starting from next position, find the first available provider
        # Cycle through full list until we find an available one
        for offset in range(1, len(all_providers) + 1):
            next_position = (last_position + offset) % len(all_providers)
            candidate = all_providers[next_position]

            # Check if this provider is available (O(1) set lookup)
            if candidate["model_id"] in available_ids:
                self.round_robin_last_used[model_name] = candidate["model_id"]
                return candidate

        # Fallback (should never reach here if available_providers is non-empty)
        selected = available_providers[0]
        self.round_robin_last_used[model_name] = selected["model_id"]
        return selected

    def suggest_provider(self, model_name: str) -> dict:
        """Suggest an available provider for the given model.

        This is the initial suggestion method that does NOT record failures.
        Use retry_suggestion() when a request fails.

        Args:
            model_name: Name of the model (e.g., "gpt-4.1")

        Returns:
            Success dict with provider config, or error dict with reason
        """
        try:
            # Validate model_name exists
            if model_name not in self.resolved_mappings:
                return {
                    "success": False,
                    "reason": "no provider available, please provide valid model_name"
                }

            # Get all providers for this model
            all_providers = self.resolved_mappings[model_name]

            # Filter out unavailable providers (in cooldown)
            available_providers = [
                p for p in all_providers
                if self.memory_store.is_available(p["model_id"])
            ]

            # Check if any providers are available
            if not available_providers:
                wait_time = self.memory_store.calculate_shortest_wait(
                    model_name,
                    MODEL_MAPPINGS
                )
                memory_state = self._get_memory_state_summary(model_name)
                return {
                    "success": False,
                    "reason": f"all providers are busy, {memory_state}. please wait for {wait_time}s"
                }

            # Select provider based on strategy (random or round-robin)
            selected = self._select_provider(model_name, available_providers)

            # Store selection for potential retry
            self.last_suggested[model_name] = selected["model_id"]

            return {
                "success": True,
                "provider": selected
            }

        except Exception as e:
            return {
                "success": False,
                "reason": f"unexpected issue: {traceback.format_exc()}"
            }

    def suggest_provider_by_id(self, model_id: str) -> dict:
        """Suggest a specific provider directly by its model_id.

        Useful as an ad-hoc override when a specific provider must be used
        (e.g. bypassing a provider with content guardrail issues).

        Unlike suggest_provider(), this method:
        - Does NOT update last_suggested (round-robin state is preserved)
        - Does NOT record any failure

        Args:
            model_id: Unique provider identifier (e.g. "openai-gpt-4.1")

        Returns:
            Success dict with provider config, or error dict with reason
        """
        try:
            # Find provider config by iterating resolved_mappings
            found_model_name = None
            found_provider = None
            for model_name, providers in self.resolved_mappings.items():
                for provider in providers:
                    if provider["model_id"] == model_id:
                        found_model_name = model_name
                        found_provider = provider
                        break
                if found_provider:
                    break

            if found_provider is None:
                return {
                    "success": False,
                    "reason": f"no provider available, {model_id!r} is not a valid model_id"
                }

            if self.memory_store.is_available(model_id):
                return {"success": True, "provider": found_provider}

            wait_time = self.memory_store.calculate_shortest_wait(
                found_model_name, MODEL_MAPPINGS
            )
            return {
                "success": False,
                "reason": f"provider {model_id!r} is unavailable, please wait for {wait_time}s"
            }
        except Exception:
            return {
                "success": False,
                "reason": f"unexpected issue: {traceback.format_exc()}"
            }

    def retry_suggestion(self, model_name: str, status_code: int) -> dict:
        """Retry provider suggestion after a failure.

        This method records the failure of the last suggested provider
        and suggests an alternative.

        Args:
            model_name: Name of the model (e.g., "gpt-4.1")
            status_code: HTTP status code from the failed request

        Returns:
            Success dict with provider config, or error dict with reason
        """
        try:
            # Record failure of last suggested provider
            if model_name in self.last_suggested:
                failed_model_id = self.last_suggested[model_name]
                self.memory_store.record_failure(failed_model_id, status_code)

            # Validate model_name exists
            if model_name not in self.resolved_mappings:
                return {
                    "success": False,
                    "reason": "no provider available, please provide valid model_name"
                }

            # Get all providers for this model
            all_providers = self.resolved_mappings[model_name]

            # Filter out unavailable providers (in cooldown)
            available_providers = [
                p for p in all_providers
                if self.memory_store.is_available(p["model_id"])
            ]

            # Check if any providers are available
            if not available_providers:
                wait_time = self.memory_store.calculate_shortest_wait(
                    model_name,
                    MODEL_MAPPINGS
                )
                memory_state = self._get_memory_state_summary(model_name)
                return {
                    "success": False,
                    "reason": f"all providers are busy, {memory_state}. please wait for {wait_time}s"
                }

            # Select provider based on strategy (random or round-robin)
            selected = self._select_provider(model_name, available_providers)

            # Update last suggested
            self.last_suggested[model_name] = selected["model_id"]

            return {
                "success": True,
                "provider": selected
            }

        except Exception as e:
            return {
                "success": False,
                "reason": f"unexpected issue: {traceback.format_exc()}"
            }

    def _get_memory_state_summary(self, model_name: str) -> str:
        """Get a summary of memory state for a specific model.

        Args:
            model_name: Name of the model

        Returns:
            Human-readable summary of unavailable providers
        """
        unavailable = self.memory_store.get_unavailable_providers(
            model_name,
            MODEL_MAPPINGS
        )

        if not unavailable:
            return "no providers in cooldown"

        return f"{len(unavailable)} provider(s) in cooldown: {', '.join(unavailable)}"

    def get_memory_state(self) -> dict:
        """Get current memory store state for debugging.

        Returns:
            Dictionary with failure records and last suggested providers
        """
        records = self.memory_store.get_all_records()

        # Convert FailureRecord objects to dicts for easier inspection
        records_dict = {
            model_id: {
                "model_id": record.model_id,
                "status_code": record.status_code,
                "recorded_at": record.recorded_at.isoformat()
            }
            for model_id, record in records.items()
        }

        return {
            "failure_records": records_dict,
            "last_suggested": self.last_suggested.copy()
        }

    def reset_memory_store(self) -> None:
        """Reset memory store and last suggested tracking.

        Useful for testing and preventing memory leaks in long-running processes.
        """
        self.memory_store.reset()
        self.last_suggested.clear()
        self.round_robin_last_used.clear()
