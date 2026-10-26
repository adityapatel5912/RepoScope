import os
from typing import Optional

PROVIDERS = {
    'groq': {
        'id': 'groq',
        'label': 'Groq',
        'base_url': 'https://api.groq.com/openai/v1',
        'default_model': 'llama-3.3-70b-versatile',
        'models': [
            'llama-3.3-70b-versatile',
            'llama-3.1-8b-instant',
            'openai/gpt-oss-120b',
        ],
    },
    'nvidia': {
        'id': 'nvidia',
        'label': 'NVIDIA NIM',
        'base_url': 'https://integrate.api.nvidia.com/v1',
        'default_model': 'meta/llama-3.3-70b-instruct',
        'models': [
            'meta/llama-3.3-70b-instruct',
            'mistralai/mistral-large-2-instruct',
        ],
    },
    'openai': {
        'id': 'openai',
        'label': 'OpenAI',
        'base_url': 'https://api.openai.com/v1',
        'default_model': 'gpt-4o-mini',
        'models': [
            'gpt-4o-mini',
            'gpt-4o',
        ],
    },
    'anthropic': {
        'id': 'anthropic',
        'label': 'Anthropic',
        'base_url': 'https://api.anthropic.com/v1',
        'default_model': 'claude-3-5-sonnet-latest',
        'models': [
            'claude-3-5-sonnet-latest',
        ],
    },
    'custom': {
        'id': 'custom',
        'label': 'Custom OpenAI-compatible',
        'base_url': '',
        'default_model': '',
        'models': [],
    },
}

def resolve_provider(
    x_ai_provider: Optional[str] = None,
    x_ai_key: Optional[str] = None,
    x_ai_model: Optional[str] = None,
    x_ai_base_url: Optional[str] = None,
) -> dict:
    """
    Return { provider, base_url, api_key, model, source }.
    Precedence: BYOK header > server env > fallback.
    """
    if x_ai_provider and x_ai_key and x_ai_provider in PROVIDERS:
        cfg = PROVIDERS[x_ai_provider]
        return {
            'provider': x_ai_provider,
            'base_url': x_ai_base_url or cfg['base_url'],
            'api_key': x_ai_key,
            'model': x_ai_model or cfg['default_model'],
            'source': 'byok',
        }
    # Fallback to server env keys
    groq_raw = os.getenv('GROQ_API_KEY') or os.getenv('GROQ_API_KEYS')
    if groq_raw:
        first_key = [k.strip() for k in groq_raw.split(',') if k.strip()][0]
        return {
            'provider': 'groq',
            'base_url': os.getenv('Base_URL_GROQ', 'https://api.groq.com/openai/v1'),
            'api_key': first_key,
            'model': os.getenv('GROQ_MODEL', os.getenv('Models_GROQ', 'llama-3.3-70b-versatile').split(',')[0].strip()),
            'source': 'server',
        }
    nvidia_raw = os.getenv('NVIDIA_API_KEY') or os.getenv('NVIDIA_API_KEYS')
    if nvidia_raw:
        first_key = [k.strip() for k in nvidia_raw.split(',') if k.strip()][0]
        return {
            'provider': 'nvidia',
            'base_url': os.getenv('Base_URL_NVIDIA', 'https://integrate.api.nvidia.com/v1'),
            'api_key': first_key,
            'model': os.getenv('NVIDIA_MODEL', os.getenv('Models_NVIDIA', 'meta/llama-3.3-70b-instruct').split(',')[0].strip()),
            'source': 'server',
        }
    openrouter_raw = os.getenv('OPENROUTER_API_KEY') or os.getenv('OPENROUTER_API_KEYS')
    if openrouter_raw:
        first_key = [k.strip() for k in openrouter_raw.split(',') if k.strip()][0]
        return {
            'provider': 'openrouter',
            'base_url': os.getenv('Base_URL_OPENROUTER', 'https://openrouter.ai/api/v1'),
            'api_key': first_key,
            'model': os.getenv('Models_OPENROUTER', 'google/gemma-4-31b-it:free').split(',')[0].strip(),
            'source': 'server',
        }
    raise RuntimeError('No AI provider configured')
