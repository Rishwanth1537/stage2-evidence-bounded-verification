# API Keys Needed

This document details all API keys referenced by the codebase and planned experimental workflows.
**Important:** Never commit API keys or paste them into chat. Store them in a local, gitignored `.env` file at the repository root.

| Environment Variable | Provider | Base URL (from code) | Scripts Using It | Referenced Model Names | Necessity for Planned Work | Pricing / Free-Tier Status |
|---|---|---|---|---|---|---|
| `GROQ_API_KEY` | Groq | `https://api.groq.com/openai/v1` | `benchmarks/llm_judge_args.py`, `benchmarks/run_judge_panel.py` | `openai/gpt-oss-120b`, `openai/gpt-oss-20b` | Needed (Judge panel baseline, fast temperature 0 natural error checks) | Verify on provider site |
| `NVIDIA_API_KEY` | NVIDIA NIM | `https://integrate.api.nvidia.com/v1` | `benchmarks/llm_judge_args.py`, `benchmarks/run_judge_panel.py`, `benchmarks/selfconsistency_bfcl.py`, `benchmarks/selfconsistency_pool.py`, `benchmarks/run_nvidia_ladder.sh` | `nvidia/nemotron-3.5-bolt-e4b`, `nvidia/nemotron-3.5-lightning-30b-a3b`, `nvidia/nemotron-3.5-super-vl-120b-a12b`, `nvidia/nemotron-3-ultra-550b-a55b` | Needed (Information-vs-size ladder, larger-model self-consistency) | Verify on provider site |
| `ANTHROPIC_API_KEY` | Anthropic | `https://api.anthropic.com/v1` (native Messages API) | `benchmarks/llm_judge_args.py`, `benchmarks/run_judge_panel.py`, `tests/test_judge_providers.py` | `claude-haiku-5-5`, `claude-sonnet-5-5`, `claude-opus-5-5`, `claude-fable-5-1` | Needed (Direct API judge panel across Claude models, repair evaluation) | Verify on provider site (billed) |
| `OPENROUTER_API_KEY` | OpenRouter | `https://openrouter.ai/api/v1` | `benchmarks/llm_judge_args.py`, `benchmarks/run_judge_panel.py`, `tests/test_judge_providers.py` | Configurable in `judge_panel.json` | Needed (Cross-family judge breadth: Llama, Mistral, Qwen) | Verify on provider site (billed) |
| `GEMINI_API_KEY` | Google Gemini | `https://generativelanguage.googleapis.com/v1beta/openai` | `benchmarks/llm_judge_args.py`, `benchmarks/run_judge_panel.py` | `gemini-2.5-flash`, `gemini-1.5-pro` | Optional (Supplementary judge family) | Verify on provider site |
| `HF_TOKEN` | Hugging Face | `https://huggingface.co` | `benchmarks/keys.py`, Hugging Face transformers/datasets loader | Pretrained models (DeBERTa-v3, RoBERTa/trf NER) and datasets | Optional (Needed only if accessing gated Hugging Face repositories) | Verify on provider site |
| `CUSTOM_API_KEY` / `ASTRA_API_KEY` | Custom OpenAI-compatible endpoint | Configurable via `--base-url` (e.g. `https://host/v1`) | `benchmarks/llm_judge_args.py`, `benchmarks/run_judge_panel.py`, `tests/test_judge_providers.py` | Any custom / self-hosted endpoint model ID | Optional (Allows routing through custom inference servers or local vLLM) | Verify on provider site |

---

### Keys / Endpoints Planned vs. Code Support Status
1. **Anthropic Native API**: Supported in `benchmarks/llm_judge_args.py` using `x-api-key` and Anthropic Messages structure (`style="anthropic"`).
2. **OpenAI Direct (`OPENAI_API_KEY`)**: Not listed under a distinct `"openai"` provider key in `PROVIDERS`, but fully supported via `--provider custom --base-url https://api.openai.com/v1 --key-env OPENAI_API_KEY`.
3. **Local / Self-Hosted Inference (Ollama / vLLM / LiteLLM)**: Supported via `--provider custom --base-url <url>`.
