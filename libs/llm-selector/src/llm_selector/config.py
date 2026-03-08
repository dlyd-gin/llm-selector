"""Model-to-provider mappings configuration."""

MODEL_MAPPINGS = {
    "gpt-5.1": [
        {
            "model_id": "openai-gpt-5.1",
            "model": "gpt-5.1",
            "api_base": "OPENAI_API_BASE",
            "api_key": "OPENAI_APIKEY"
        }
    ],
    "gpt-5.2": [
        {
            "model_id": "openai-gpt-5.2",
            "model": "gpt-5.2",
            "api_base": "OPENAI_API_BASE",
            "api_key": "OPENAI_APIKEY"
        }
    ],
    "gpt-4.1": [
        {
            "model_id": "openai-gpt-4.1",
            "model": "gpt-4.1",
            "api_base": "OPENAI_API_BASE",
            "api_key": "OPENAI_APIKEY"
        },
        {
            "model_id": "azure-aueast-gpt-4.1",
            "model": "gpt-4.1",
            "api_base": "AZURE_OPENAI_API_BASE_AUEAST",
            "api_key": "AZURE_OPENAI_APIKEY_AUEAST",
            "api_version": "2024-02-15-preview"
        },
        {
            "model_id": "azure-northcentralus-gpt-4.1",
            "model": "gpt-4.1",
            "api_base": "AZURE_OPENAI_API_BASE_NORTHCENTRALUS",
            "api_key": "AZURE_OPENAI_APIKEY_NORTHCENTRALUS",
            "api_version": "2024-02-15-preview"
        },
        {
            "model_id": "azure-southcentralus-gpt-4.1",
            "model": "gpt-4.1",
            "api_base": "AZURE_OPENAI_API_BASE_SOUTHCENTRALUS",
            "api_key": "AZURE_OPENAI_APIKEY_SOUTHCENTRALUS",
            "api_version": "2024-02-15-preview"
        }
    ],
    "claude-sonnet-4-5": [
        {
            "model_id": "bedrock-claude-sonnet-4-5",
            "model": "bedrock/global.anthropic.claude-sonnet-4-5-20250929-v1:0",
            "aws_bedrock": {
                "aws_region_name": "us-west-2",
                "anthropic_beta": "context-1m-2025-08-07"
            }
        }
    ],
}
