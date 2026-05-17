"""
LLM module for calling OpenRouter API
"""

import os
import requests
from typing import List, Dict, Any, Optional

def call_llm(prompt: str, model: str = "openai/gpt-3.5-turbo") -> str:
    """
    Call OpenRouter LLM API (Legacy single prompt)
    """
    return call_llm_chat([{"role": "user", "content": prompt}], model)

def call_llm_chat(messages: List[Dict[str, str]], model: str = "openai/gpt-3.5-turbo") -> str:
    """
    Call OpenRouter LLM API with chat history
    
    Args:
        messages: List of message dictionaries, e.g., [{"role": "user", "content": "hello"}]
        model: Model to use (default: openai/gpt-3.5-turbo)
    
    Returns:
        LLM response text
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
        "max_tokens": 4000
    }
    
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=60
        )
        response.raise_for_status()
        
        data = response.json()
        return data["choices"][0]["message"]["content"]
    
    except requests.exceptions.RequestException as e:
        raise Exception(f"LLM API call failed: {str(e)}")

# --- Prompts ---

LATEX_GENERATION_SYSTEM_PROMPT = """You are an expert LaTeX developer and resume writer.
Your task is to create a clean, professional, and easily compilable LaTeX resume based on the provided user resume data and job description.
Use the `article` document class and standard packages like `geometry`, `hyperref`, `enumitem`, `titlesec`.
Do not use any obscure packages or custom fonts that require XeLaTeX or LuaLaTeX. The code must compile with standard pdflatex.

Output ONLY valid LaTeX code. Do not include markdown formatting like ```latex ... ```. 
Start your response exactly with \\documentclass and end exactly with \\end{document}."""

AGENT_SYSTEM_PROMPT = """You are an expert AI Resume Assistant. You help users improve their resume to match a job description.
The user might ask for advice, or they might ask you to modify their resume text.

When the user asks for a modification to the resume:
1. Provide the updated LaTeX code for the resume.
2. In your response, the LaTeX code MUST be enclosed in ```latex\n ... \n``` tags. 
3. Briefly explain the changes you made before or after the code block.

Keep your tone professional, encouraging, and focused on maximizing their chances of landing the job."""