import json

from .base import PROMPT, content, post, ProviderError
from .schemas import SCHEMA


class GeminiProvider:
    def __init__(self, config):
        self.config = config

    def generate(self, article):
        c = self.config

        # Official GA Interactions API endpoint
        url = "https://generativelanguage.googleapis.com/v1/interactions"

        headers = {
            "x-goog-api-key": c.api_key,
            "Content-Type": "application/json",
        }

        payload = {
            "model": c.model,
            "input": PROMPT + "\n\n" + content(article),

            "response_format": {
                "type": "text",
                "mime_type": "application/json",
                "schema": SCHEMA,
            },
        }

        result = post(
            url,
            headers,
            payload,
            c.timeout,
        )

        try:
            steps = result.get("steps")

            if not isinstance(steps, list):
                raise ValueError("Missing steps")

            text_parts = []

            for step in steps:
                if not isinstance(step, dict):
                    continue

                if step.get("type") != "model_output":
                    continue

                step_content = step.get("content")

                if not isinstance(step_content, list):
                    continue

                for item in step_content:
                    if not isinstance(item, dict):
                        continue

                    if item.get("type") != "text":
                        continue

                    text = item.get("text")

                    if isinstance(text, str) and text.strip():
                        text_parts.append(text)

            if not text_parts:
                raise ValueError("No model output text")

            raw_text = "".join(text_parts).strip()

            value = json.loads(raw_text)

        except (
            KeyError,
            IndexError,
            TypeError,
            ValueError,
            AttributeError,
            json.JSONDecodeError,
        ):
            raise ProviderError(
                "invalid_or_incomplete_response"
            ) from None

        usage = result.get("usage")

        if not isinstance(usage, dict):
            usage = {}

        input_tokens = (
            usage.get("input_tokens")
            or usage.get("inputTokens")
        )

        output_tokens = (
            usage.get("output_tokens")
            or usage.get("outputTokens")
        )

        total_tokens = (
            usage.get("total_tokens")
            or usage.get("totalTokens")
        )

        return value, {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
        }