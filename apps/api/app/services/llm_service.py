import os
import time
from typing import List, Callable, Any
from llama_index.llms.openai import OpenAI
from llama_index.llms.gemini import Gemini
import logging

logger = logging.getLogger(__name__)

class LLMLoadBalancer:
    def __init__(self):
        self.llms = []
        self._initialize_llms()
        self.current_index = 0
        
    def _initialize_llms(self):
        """Load all keys and create LLM instances for each."""
        # 1. OpenRouter
        openrouter_keys = [k for k in os.environ.get("OPENROUTER_KEYS", "").split(",") if k]
        for key in openrouter_keys:
            self.llms.append(OpenAI(
                model="openai/gpt-4o-mini",
                api_key=key,
                api_base="https://openrouter.ai/api/v1",
                temperature=0.1
            ))
            
        # 2. Groq
        groq_keys = [k for k in os.environ.get("GROQ_KEYS", "").split(",") if k]
        for key in groq_keys:
            self.llms.append(OpenAI(
                model="llama3-8b-8192",
                api_key=key,
                api_base="https://api.groq.com/openai/v1",
                temperature=0.1
            ))
            
        # 3. Gemini
        gemini_keys = [k for k in os.environ.get("GEMINI_KEYS", "").split(",") if k]
        for key in gemini_keys:
            self.llms.append(Gemini(
                model="models/gemini-1.5-flash",
                api_key=key,
                temperature=0.1
            ))
            
        if not self.llms:
            logger.warning("No API keys found for LLM Load Balancer. AI requests will fail.")
            
    def execute_with_fallback(self, execute_fn: Callable[[Any], Any]) -> Any:
        """
        Executes a function (which uses the current LLM). 
        If it hits a rate limit or auth error, it rotates the LLM and retries.
        execute_fn should accept a single argument: the LLM instance to use.
        """
        if not self.llms:
            raise ValueError("No LLMs configured in Load Balancer.")
            
        attempts = 0
        max_attempts = len(self.llms)
        
        while attempts < max_attempts:
            current_llm = self.llms[self.current_index]
            try:
                # Attempt to execute the function with the current LLM
                return execute_fn(current_llm)
                
            except Exception as e:
                error_msg = str(e).lower()
                # Check if it's a rate limit or auth error
                if "429" in error_msg or "rate limit" in error_msg or "401" in error_msg or "unauthorized" in error_msg or "invalid" in error_msg:
                    logger.warning(f"LLM {self.current_index} failed (Error: {e}). Rotating to next key...")
                    # Rotate key
                    self.current_index = (self.current_index + 1) % len(self.llms)
                    attempts += 1
                    # Slight backoff before retry
                    time.sleep(1)
                else:
                    # If it's a different kind of error (e.g. bad request), don't failover
                    raise e
                    
        raise Exception("All available AI keys failed or hit rate limits.")

llm_load_balancer = LLMLoadBalancer()
