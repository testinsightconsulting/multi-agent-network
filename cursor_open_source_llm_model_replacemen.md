# Open-source LLM model replacement
_Exported on 1/30/2026 at 11:51:29 EST from Cursor (2.4.21)_

---

**User**

Examining this solution, is it possible to replace the LLM Model Gemini with a comparative opern source LLM model?

---

**Cursor**


Exploring the codebase to see how Gemini is used and whether we can replace it with an open-source LLM.



Inspecting how the Gemini client is used for generation and tool calling:



Checking the API helper that performs the actual Gemini call:



Yes. You can replace Gemini with a comparable open-source LLM, but you need to match the features the code uses and add a small abstraction layer.

---

## How Gemini is used today

1. **SDK**  
   The app uses the **Google `genai`** client (`google-genai`), e.g. in `device_agent.py` and `concierge_agent.py`:
   - `genai.Client(api_key=gemini_api_key)`
   - `client.models.generate_content(...)` with `types.GenerateContentConfig(system_instruction=..., tools=...)`

2. **Single entry point**  
   All generation goes through `src/utils/api_helper.py` → `generate_content_with_adaptive_retry()`, which calls:
   - `client.models.generate_content(model=..., contents=history, config=...)`
   - Uses `types.Content`, `types.Part`, `types.GenerateContentConfig`, `types.GenerateContentResponse`.

3. **Features that must be supported by a replacement**
   - **System instruction** – used in both Concierge and Device agents.
   - **Multi-turn history** – list of `types.Content` (user/model turns).
   - **Function/tool calling** – the critical part:
     - Tools are passed as Python callables.
     - Model returns `part.function_call` (name + args).
     - Code runs the tool and appends `types.Part.from_function_response(...)`.
     - Loop continues until the model returns only text (no tool calls).

4. **Where the model name is set**  
   - `device_agent.py` line 584: `model="gemini-2.5-flash"`  
   - `concierge_agent.py` line 266: `model="gemini-2.5-flash"`  
   - API key is passed from the CLI (`GEMINI_API_KEY`) into both agents.

So any replacement backend must support: **chat with system instruction + history + tool/function calling**.

---

## Is it possible to use an open-source model?

Yes. You need:

1. An **open-source (or self-hosted) model** that supports **tool/function calling** (e.g. Llama 3.2, Qwen2.5, Mistral, or another with tool-use support).
2. A **client/API** that exposes:
   - Chat with system instruction and message history.
   - Tool definitions and tool-call/tool-result in the same loop you have now.
3. A **thin abstraction** in your app so agents don’t depend on `genai` directly.

---

## Practical options (open-source / local)

| Option | Notes |
|--------|--------|
| **Ollama** | Run models locally; some (e.g. Llama 3.2, Qwen2.5) support tools. Can expose an OpenAI-compatible API. |
| **OpenAI-compatible API** | Many local servers (vLLM, llama.cpp, LM Studio, etc.) expose an OpenAI-like API; tool calling depends on the server and model. |
| **LiteLLM** | Can proxy to Ollama, vLLM, etc. and normalize to one interface (e.g. OpenAI format), including tools. |
| **Hugging Face / Transformers** | Possible with an agent/tool loop on top; more custom code and model support for tools varies. |

So yes: you can replace Gemini with a comparable open-source model **if** that model (and its API) supports **function/tool calling** and you adapt the client interface.

---

## What you’d change in this repo (conceptually)

- **Abstraction**
  - Define an internal interface: e.g. “generate from history + system instruction + tools, return text + optional tool calls.”
  - Implement that for:
    - **Gemini** (current `genai` usage in `api_helper` and agents).
    - **Open-source** (e.g. one implementation that talks to an OpenAI-compatible or Ollama endpoint).
- **Message/tool format**
  - Today: Google `types.Content` / `Part` / `function_call` / `from_function_response`.
  - New backend: usually OpenAI-style messages and `tool_calls` / `tool` results. You’d convert between your internal “history + tool_calls” and the provider’s format inside the abstraction.
- **Config**
  - Swap API key / URL / model name via config or env (e.g. `LLM_PROVIDER=gemini|ollama|openai_compat`, `LLM_MODEL=...`, and corresponding keys).
- **Web search**
  - `src/knowledge/web_search.py` currently refers to “Gemini’s web search”; that’s a separate feature. Replacing Gemini doesn’t force you to change it; you could keep a separate search API or another provider later.

So: **yes, it’s possible to replace the LLM model Gemini with a comparable open-source LLM**, as long as you pick a model and API that support tool calling and you introduce a small client abstraction and config so the rest of the solution stays provider-agnostic.

