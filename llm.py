import requests
import json
import logging
from typing import Optional
from dataclasses import dataclass
from enum import Enum


class ModelType(Enum):
    """Supported model types"""
    LLAMA2_UNCENSORED = "llama2-uncensored"
    DEEPSEEK_R1__1_5B = "deepseek-r1:1.5b"


@dataclass
class LLMConfig:
    """Configuration for LLM API calls"""
    base_url: str = "http://localhost:11434"
    model: str = "llama2-uncensored"
    temperature: float = 0.7
    max_tokens: int = 2048
    top_p: float = 0.9
    stream: bool = False


class LLMWrapper:
    """
    A wrapper for calling locally hosted LLMs via Ollama API.
    Intended to be used across the astroturf project.
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        """
        Initialize the LLM wrapper.

        Args:
            config: Configuration for the LLM API calls
        """
        self.config = config or LLMConfig()
        self.logger = logging.getLogger(__name__)

    def generate_response(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream_output: bool = False
    ) -> str:
        """
        Generate a response from the local Ollama API.

        Args:
            prompt: The prompt to send to the model
            model: The model to use (overrides config if provided)
            temperature: Generation temperature (override config if provided)
            max_tokens: Maximum generated tokens (override config if provided)
            stream_output: Whether to show streaming output

        Returns:
            The generated response text

        Raises:
            requests.RequestException: If the API call fails
            json.JSONDecodeError: If the response is not valid JSON
        """
        url = f"{self.config.base_url}/api/generate"

        # Use provided parameters or fall back to config
        model_name = model or self.config.model
        temp = temperature or self.config.temperature
        tokens = max_tokens or self.config.max_tokens

        data = {
            "model": model_name,
            "prompt": prompt,
            "temperature": temp,
            "max_tokens": tokens,
            "top_p": self.config.top_p,
            "stream": False  # Current models don't support streaming
        }

        try:
            response = requests.post(url, json=data, timeout=30)
            response.raise_for_status()

            full_response = ""
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    try:
                        response_data = json.loads(decoded_line)
                        response_text = response_data.get("response", "")
                        full_response += response_text

                        if stream_output:
                            self.logger.info(response_text)

                    except json.JSONDecodeError as e:
                        self.logger.warning(f"Failed to parse response: {e}")
                        continue

            return full_response

        except requests.RequestException as e:
            self.logger.error(f"API request failed: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error during generation: {e}")
            raise
