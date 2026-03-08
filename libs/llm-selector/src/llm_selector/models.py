"""Data models and type definitions for provider selector."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class AwsBedrockConfig:
    """Configuration specific to AWS Bedrock providers.

    Attributes:
        aws_region_name: AWS region for Bedrock providers
        anthropic_beta: Beta features header for Anthropic models
    """
    aws_region_name: str
    anthropic_beta: Optional[str] = None


@dataclass
class ProviderConfig:
    """Configuration for a single provider.

    Attributes:
        model_id: Unique identifier for this provider configuration
        model: Model identifier string (e.g., "gpt-4.1")
        api_base: Base URL for the API endpoint
        api_key: API key or environment variable name
        api_version: API version string (for Azure)
        aws_bedrock: AWS Bedrock-specific configuration
    """
    model_id: str
    model: str
    api_base: Optional[str] = None
    api_key: Optional[str] = None
    api_version: Optional[str] = None
    aws_bedrock: Optional[AwsBedrockConfig] = None


@dataclass
class FailureRecord:
    """Record of a provider failure.

    Attributes:
        model_id: Unique identifier of the failed provider
        status_code: HTTP status code of the failure
        recorded_at: Timestamp when the failure was recorded
    """
    model_id: str
    status_code: int
    recorded_at: datetime


@dataclass
class SuccessResponse:
    """Successful provider selection response.

    Attributes:
        success: Always True for success responses
        provider: Dictionary containing provider configuration
    """
    success: bool = True
    provider: dict = field(default_factory=dict)


@dataclass
class ErrorResponse:
    """Error response from provider selection.

    Attributes:
        success: Always False for error responses
        reason: Human-readable error message
    """
    success: bool = False
    reason: str = ""
