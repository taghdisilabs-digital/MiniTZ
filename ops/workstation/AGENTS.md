# Biella Workstation Agent Policy

- Execute directly when the task and authority are clear.
- Prefer local Qwen for routine bulk work, iteration, parsing, summarization, and inexpensive code reasoning.
- Keep every configured production provider and tool available; choose by capability, latency, cost, and task fit.
- Use one external provider by default. Fan out to multiple providers only when comparison, fallback, or independent validation adds value.
- Do not repeat a successful provider call unless new evidence or a distinct comparison requires it.
- Keep terminal/tool narration compact. Report successful calls as concise summaries instead of dumping response bodies.
- Surface full logs, traces, or provider payloads only for failures, diagnostics, or when explicitly requested.
- Continue automatically after recoverable provider failures by selecting another appropriate configured tool when that preserves task correctness.
- Never print secret values, bearer tokens, API keys, refresh tokens, or credential file contents.
- Modal, Saturn, Cloudflare, Groq, Cerebras, OpenRouter, Mistral, Tavily, Gemini/Google, Docker, GitHub, and local Qwen are valid Biella production tools when configured.
- Preserve current project authority, accepted state, source boundaries, and explicit task scope.
- Do not invent approval, deployment, synchronization, publication, or provider success without observed evidence.
- Exa and Pexels are valid web/media retrieval tools; use them only when their specialized retrieval adds value over Tavily or native search.
- Pinecone and Qdrant are valid vector stores; Deepgram, AssemblyAI, and ElevenLabs are valid speech/audio tools; Stability AI and Cloudinary are valid media-production tools; Supabase, Neon, and Upstash are valid data/runtime tools; Axiom is a valid observability tool when configured.
