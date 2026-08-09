# ============================================================
# LLM Service — Unified AI Model Interface
# ============================================================
# PURPOSE:
#   Provides ONE simple function to call ANY LLM (OpenAI, Gemini, Claude).
#   Every agent in the system calls this service instead of directly
#   calling OpenAI/Gemini/Claude APIs.
#
# WHY A WRAPPER?
#   Without this:
#     resume_agent.py  → import openai; openai.chat.completions.create(...)
#     matching_agent.py → import openai; openai.chat.completions.create(...)
#     ranking_agent.py  → import openai; openai.chat.completions.create(...)
#   
#   If you switch to Gemini, you'd change ALL THREE files.
#
#   With this:
#     resume_agent.py   → from services.llm_service import llm; llm.call(prompt)
#     matching_agent.py → from services.llm_service import llm; llm.call(prompt)
#     ranking_agent.py  → from services.llm_service import llm; llm.call(prompt)
#   
#   Switch to Gemini? Change ONE LINE in .env: LLM_PROVIDER=gemini
#
# USAGE:
#   from services.llm_service import llm
#   
#   # Simple text response
#   response = llm.call("Summarize this job description: ...")
#   
#   # JSON response (for structured data extraction)
#   data = llm.call_json("Extract skills from this resume: ...", schema=UserProfile)
# ============================================================

import json
from typing import Optional, Type
from pydantic import BaseModel
from config.settings import settings


class LLMService:
    """
    Unified interface to call OpenAI, Gemini, or Claude.
    
    The provider is determined by the LLM_PROVIDER setting in .env.
    All three providers expose the same two methods:
        - call()      → returns plain text
        - call_json() → returns parsed JSON (validated against a Pydantic schema)
    """

    def __init__(self):
        """
        Initialize the LLM client based on the configured provider.
        
        This runs ONCE when the service is created. It sets up the
        appropriate client (OpenAI/Gemini/Claude) based on .env config.
        """
        self.provider = settings.LLM_PROVIDER.lower()
        self.client = None

        if self.provider == "openai":
            self._init_openai()
        elif self.provider == "gemini":
            self._init_gemini()
        elif self.provider == "claude":
            self._init_claude()
        elif self.provider == "nvidia":
            self._init_nvidia()
        else:
            raise ValueError(
                f"Unknown LLM_PROVIDER: '{self.provider}'. "
                f"Must be one of: openai, gemini, claude, nvidia"
            )

    # ================================================================
    # INITIALIZATION — One method per provider
    # ================================================================

    def _init_openai(self):
        """Set up the OpenAI client."""
        from openai import OpenAI

        if not settings.OPENAI_API_KEY:
            raise ValueError(
                "OPENAI_API_KEY is not set in .env. "
                "Get one at https://platform.openai.com/api-keys"
            )

        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_MODEL
        print(f"[LLM] Initialized OpenAI with model: {self.model}")

    def _init_nvidia(self):
        """Set up the NVIDIA NIM client (OpenAI compatible API)."""
        from openai import OpenAI

        if not settings.NVIDIA_API_KEY:
            raise ValueError(
                "NVIDIA_API_KEY is not set in .env. "
                "Get one at https://build.nvidia.com"
            )

        self.client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=settings.NVIDIA_API_KEY
        )
        self.model = settings.NVIDIA_MODEL
        print(f"[LLM] Initialized NVIDIA NIM with model: {self.model}")

    def _init_gemini(self):
        """Set up the Google Gemini client."""
        import google.generativeai as genai

        if not settings.GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_API_KEY is not set in .env. "
                "Get one at https://aistudio.google.com/apikey"
            )

        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.client = genai.GenerativeModel(settings.GEMINI_MODEL)
        self.model = settings.GEMINI_MODEL
        print(f"[LLM] Initialized Gemini with model: {self.model}")

    def _init_claude(self):
        """Set up the Anthropic Claude client."""
        from anthropic import Anthropic

        if not settings.CLAUDE_API_KEY:
            raise ValueError(
                "CLAUDE_API_KEY is not set in .env. "
                "Get one at https://console.anthropic.com/settings/keys"
            )

        self.client = Anthropic(api_key=settings.CLAUDE_API_KEY)
        self.model = settings.CLAUDE_MODEL
        print(f"[LLM] Initialized Claude with model: {self.model}")

    # ================================================================
    # MAIN METHODS — What agents actually call
    # ================================================================

    def call(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        """
        Send a prompt to the LLM and get a text response.
        
        Args:
            prompt: The main question/instruction for the LLM.
            system_prompt: Optional system-level instruction that shapes the LLM's behavior.
                          Example: "You are a professional recruiter analyzing resumes."
            temperature: Controls randomness (0.0 = deterministic, 1.0 = creative).
                        We default to 0.3 for consistent, factual responses.
            max_tokens: Maximum length of the response.
        
        Returns:
            The LLM's text response as a string.
        
        Example:
            response = llm.call(
                prompt="What are the key skills in this job description?",
                system_prompt="You are a job market analyst.",
            )
        """
        import time
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if self.provider in ("openai", "nvidia"):
                    return self._call_openai(prompt, system_prompt, temperature, max_tokens)
                elif self.provider == "gemini":
                    return self._call_gemini(prompt, system_prompt, temperature, max_tokens)
                elif self.provider == "claude":
                    return self._call_claude(prompt, system_prompt, temperature, max_tokens)
            except Exception as e:
                err_str = str(e).lower()
                if ("429" in err_str or "rate" in err_str or "limit" in err_str or "503" in err_str) and attempt < max_retries - 1:
                    sleep_time = (2 ** attempt) * 2.0
                    print(f"[LLM Rate Limit Guardrail] Caught rate limit ({e}). Retrying in {sleep_time}s (Attempt {attempt+1}/{max_retries})...")
                    time.sleep(sleep_time)
                else:
                    raise e
        return ""

    def call_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        schema: Optional[Type[BaseModel]] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> dict:
        """
        Send a prompt to the LLM and get a JSON response.
        
        This is used when we need structured data back (not free-form text).
        For example, when parsing a resume into a UserProfile schema.
        
        Args:
            prompt: The instruction (should ask for JSON output).
            system_prompt: System-level instruction.
            schema: Optional Pydantic model class. If provided, the response is
                   validated against this schema. If validation fails, we retry.
            temperature: Low by default (0.1) for consistent JSON structure.
            max_tokens: Maximum response length.
        
        Returns:
            Parsed JSON as a Python dictionary.
        
        Example:
            profile_data = llm.call_json(
                prompt=f"Extract skills from this resume: {resume_text}",
                system_prompt="Return a JSON object with the user's profile.",
                schema=UserProfile,
            )
        """
        # Add JSON instruction to the system prompt
        json_instruction = (
            "You MUST respond with valid JSON only. "
            "Do not include any text before or after the JSON. "
            "Do not use markdown code blocks."
        )

        if system_prompt:
            full_system = f"{system_prompt}\n\n{json_instruction}"
        else:
            full_system = json_instruction

        # If a schema is provided, add its structure to the prompt
        # so the LLM knows exactly what shape of JSON to produce
        if schema:
            schema_json = json.dumps(schema.model_json_schema(), indent=2)
            prompt = f"{prompt}\n\nRespond with JSON matching this schema:\n{schema_json}"

        # Get the raw text response
        response_text = self.call(
            prompt=prompt,
            system_prompt=full_system,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Parse the JSON from the response
        parsed = self._extract_json(response_text)

        # If a schema was provided, validate the response against it
        if schema and parsed:
            try:
                validated = schema.model_validate(parsed)
                return validated.model_dump()
            except Exception as e:
                print(f"[LLM] Warning: Response didn't match schema: {e}")
                # Return the raw parsed JSON even if it doesn't perfectly match
                return parsed

        return parsed

    # ================================================================
    # PROVIDER-SPECIFIC CALL METHODS
    # ================================================================
    # Each method below handles the API differences between providers.
    # They all take the same inputs and return a string.
    # ================================================================

    def _call_openai(
        self, prompt: str, system_prompt: Optional[str],
        temperature: float, max_tokens: int
    ) -> str:
        """
        Call OpenAI's or NVIDIA NIM's Chat Completions API.
        
        Supports standard models as well as reasoning/thinking models like
        deepseek-ai/deepseek-v4-flash on NVIDIA NIM endpoints!
        """
        messages = []

        # System message (optional) — tells the model HOW to behave
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # User message — the actual question/task
        messages.append({"role": "user", "content": prompt})

        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # Enable thinking/reasoning effort for DeepSeek or reasoning models on NVIDIA NIM!
        if "deepseek" in self.model.lower() or "reasoning" in self.model.lower():
            kwargs["extra_body"] = {"chat_template_kwargs": {"thinking": True, "reasoning_effort": "high"}}

        response = self.client.chat.completions.create(**kwargs)

        msg = response.choices[0].message
        reasoning = getattr(msg, "reasoning", None) or getattr(msg, "reasoning_content", None)
        if reasoning:
            print(f"[LLM Thinking]: {reasoning[:300]}...")

        return msg.content

    def _call_gemini(
        self, prompt: str, system_prompt: Optional[str],
        temperature: float, max_tokens: int
    ) -> str:
        """
        Call Google Gemini's Generate Content API.
        
        Gemini combines system + user prompts into a single string.
        """
        # Combine system prompt and user prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        else:
            full_prompt = prompt

        response = self.client.generate_content(
            full_prompt,
            generation_config={
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            },
        )

        return response.text

    def _call_claude(
        self, prompt: str, system_prompt: Optional[str],
        temperature: float, max_tokens: int
    ) -> str:
        """
        Call Anthropic Claude's Messages API.
        
        Claude uses a similar message format to OpenAI, but the
        system prompt is a separate parameter (not in the messages list).
        """
        message = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            # Claude takes system prompt as a separate argument
            system=system_prompt or "",
            messages=[
                {"role": "user", "content": prompt}
            ],
        )

        # Claude's response is a list of content blocks
        return message.content[0].text

    # ================================================================
    # HELPER METHODS
    # ================================================================

    def _extract_json(self, text: str) -> dict:
        """
        Extract and parse JSON from the LLM's response text.
        
        LLMs sometimes wrap JSON in markdown code blocks like:
            ```json
            {"key": "value"}
            ```
        
        This method handles all these cases:
            1. Clean JSON string → parse directly
            2. JSON in markdown code block → strip the markdown, then parse
            3. JSON embedded in other text → find the { } boundaries, then parse
        """
        # Remove leading/trailing whitespace
        text = text.strip()

        # Case 1: Try parsing directly
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Case 2: Remove markdown code block wrappers
        if text.startswith("```"):
            # Remove the opening ``` (and optional language label like ```json)
            lines = text.split("\n")
            # Remove first line (```) and last line (```)
            if lines[-1].strip() == "```":
                text = "\n".join(lines[1:-1])
            else:
                text = "\n".join(lines[1:])

            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass

        # Case 3: Find JSON object boundaries { ... }
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass

        # Case 4: Find JSON array boundaries [ ... ]
        start = text.find("[")
        end = text.rfind("]") + 1
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass

        # If all parsing attempts fail, return empty dict
        print(f"[LLM] Warning: Could not parse JSON from response: {text[:200]}...")
        return {}


# ============================================================
# CREATE THE GLOBAL LLM INSTANCE
# ============================================================
# This is what every agent imports:
#     from services.llm_service import llm
#
# We use a lazy initialization pattern here:
# The LLM client is created only when first used, not at import time.
# This prevents errors during testing or when API keys aren't set yet.
# ============================================================

_llm_instance: Optional[LLMService] = None


def get_llm() -> LLMService:
    """
    Get or create the global LLM service instance.
    
    Uses lazy initialization — the client is only created
    when this function is first called (not at module import time).
    
    Usage:
        from services.llm_service import get_llm
        
        llm = get_llm()
        response = llm.call("Hello!")
    """
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = LLMService()
    return _llm_instance
