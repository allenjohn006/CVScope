"""
LLM module for calling OpenRouter API
"""

import os
import requests
from typing import List, Dict, Optional


def call_llm(prompt: str, model: str = "openai/gpt-3.5-turbo") -> str:
    """
    Call OpenRouter LLM API (Legacy single prompt)
    """
    return call_llm_chat([{"role": "user", "content": prompt}], model)


def call_llm_chat(messages: List[Dict[str, str]], model: str = "openai/gpt-3.5-turbo") -> str:
    """
    Call OpenRouter LLM API with chat history.
    """
    api_key = os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        raise ValueError("OPENROUTER_API_KEY environment variable not set")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 4000,
    }

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    except requests.exceptions.RequestException as e:
        raise Exception(f"LLM API call failed: {str(e)}")


# ---------------------------------------------------------------------------
# System Prompts
# ---------------------------------------------------------------------------

LATEX_GENERATION_SYSTEM_PROMPT = """You are an expert LaTeX developer and resume writer.

Your task is to produce a clean, professional, ATS-optimised LaTeX resume that:
1. Uses the candidate's ORIGINAL experience, projects, education, and contact details exactly as provided.
2. Intelligently weaves in the MISSING KEYWORDS and SKILLS identified in the evaluation suggestions WITHOUT fabricating experience — add them as honest bullet-point enhancements, skill-section entries, or rephrased descriptions wherever they genuinely fit.
3. Uses the `article` document class and only standard packages: `geometry`, `hyperref`, `enumitem`, `titlesec`, `parskip`, `fontenc`, `inputenc`. Do NOT use XeLaTeX-only or LuaLaTeX-only packages.
4. Produces output that compiles cleanly with `pdflatex`.

Output ONLY valid LaTeX code. Do NOT wrap the output in markdown fences (no ```latex). 
Start your response exactly with \\documentclass and end exactly with \\end{document}."""


AGENT_SYSTEM_PROMPT = """You are an expert AI Resume Assistant. You help users improve their resume to match a job description.

When the user asks for a text modification to the resume:
1. Return the full updated LaTeX code enclosed in ```latex\\n...\\n``` fences.
2. Briefly explain the changes before or after the code block.

Keep your tone professional and encouraging."""