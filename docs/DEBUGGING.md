# Debugging Concierge → Specialist Flow

Use this to break and step through the call when the Concierge routes a question to a Specialist Agent (e.g. "what is the current configuration of the Arista?").

## Why the conversation can "pause" (fixed)

If you only saw "Concierge calling specialist" and then "I have queried... awaiting response" with no specialist debug lines, the cause was a **deadlock**: the Concierge's `query_specialist` tool runs inside the main event loop. The code used to return "pending" when the loop was already running, so the message was never sent and the specialist was never called. The fix: we use **nest_asyncio** so that the tool can call `run_until_complete(send_and_wait)` from inside the running loop; the loop then processes the MessageBus and the specialist receives and responds. Ensure `nest-asyncio` is installed and that the CLI applies it to the event loop (see `agent_cli.py`).

## Enable debug logging

Set the environment variable so you see each step in the flow:

```bash
# Windows PowerShell
$env:TOPOLOGY_DEBUG="1"
python main.py --topology Zero_Touch_Lab_Orchestration_Topology.yaml

# Windows CMD
set TOPOLOGY_DEBUG=1
python main.py --topology Zero_Touch_Lab_Orchestration_Topology.yaml

# Linux / macOS
TOPOLOGY_DEBUG=1 python main.py --topology Zero_Touch_Lab_Orchestration_Topology.yaml
```

You’ll see lines like:

- `[Concierge→Specialist] Concierge calling specialist` (Concierge invokes `query_specialist`)
- `[Concierge→Specialist] MessageBus routing to specialist` (message handed to specialist)
- `[Concierge→Specialist] Specialist received query` (specialist’s `_handle_message`)
- `[Concierge→Specialist] Specialist _process_query start` (specialist starts Gemini)
- `[Concierge→Specialist] Specialist _process_query done` (specialist finished)
- `[Concierge→Specialist] Specialist sending response` (response back to Concierge)
- `[Concierge→Specialist] MessageBus specialist responded`
- `[Concierge→Specialist] Concierge received response from specialist`
- **Inside the specialist:** `[Concierge→Specialist] Specialist tool: read_device_configuration` (and other tools: `execute_device_command`, `analyze_configuration`, `validate_feature_configuration`, `query_local_knowledge_base`, `search_web_documentation`, `query_other_agent`, `get_topology_info`)

## Breaking inside the specialist task

To **break inside the specialist** and validate it is taking the right steps to answer the Concierge’s question:

1. Set a breakpoint at **Specialist receives the query** (`device_agent._handle_message`, first line after docstring).
2. Run with `TOPOLOGY_DEBUG=1`, ask e.g. “what is the current configuration of the Arista?”.
3. When the breakpoint hits, **Step Into** into `_process_query`. The specialist will call Gemini; Gemini may then call one or more tools. Each tool has a breakpoint so you can confirm the sequence.

### Specialist tool breakpoints (validate steps)

All in **`src/agent/device_agent.py`**. Set breakpoints at the line with `# BREAKPOINT: Specialist step — ...` in each function.

| Tool | Function | What to validate |
|------|----------|------------------|
| **read_device_configuration** | `read_device_configuration` | Specialist is reading config (e.g. for “what is the configuration?”). Inspect `section` (optional). |
| **execute_device_command** | `execute_device_command` | Specialist is running a CLI command. Inspect `command`. |
| **analyze_configuration** | `analyze_configuration` | Specialist is analyzing config + RAG best practices. Inspect `feature`. |
| **validate_feature_configuration** | `validate_feature_configuration` | Specialist is validating a feature against docs. Inspect `feature`, `expected_behavior`. |
| **query_local_knowledge_base** | `query_local_knowledge_base` | Specialist is looking up local docs. Inspect `query`. |
| **search_web_documentation** | `search_web_documentation` | Specialist is searching the web. Inspect `query`. |
| **suggest_device_commands** | `suggest_device_commands` | Specialist uses catalog + RAG + web to propose commands. Inspect `question`, returned `commands`. |
| **resolve_and_execute_commands** | `resolve_and_execute_commands` | Specialist resolves and runs commands. Inspect `commands`, `outputs`. |
| **query_other_agent** | `query_other_agent` | Specialist is asking another device agent. Inspect `target_agent_id`, `question`. |
| **get_topology_info** | `get_topology_info` | Specialist is listing other agents in the topology. |

### Example: “What is the current configuration of the Arista?”

Expected specialist steps:

1. **Breakpoint:** `_handle_message` — specialist receives “What is the current configuration?” (or similar).
2. **Breakpoint:** `_process_query` start — specialist sends the query to Gemini.
3. **Breakpoint:** `read_device_configuration` — Gemini should call this (with `section=None` or a specific section). **Validate:** `device` = “Arista DUT”, then step through to see `config` returned from `device_interface.get_configuration()`.
4. Optionally: `analyze_configuration` or other tools if the model decides to.
5. **Breakpoint:** `_process_query` done then `_handle_message` (sending response) — specialist returns the answer to the Concierge.

If `read_device_configuration` is never hit, the specialist (Gemini) may be answering without reading config; check system instruction and tool definitions.

## Breakpoint locations (step through in IDE)

Set breakpoints at these spots to follow the Concierge → Specialist path.

### 1. Concierge decides to call a specialist

**File:** `src/agent/concierge_agent.py`  
**Function:** `query_specialist`  
**Line:** Just before `msg = AgentMessage(...)` (comment: `# BREAKPOINT: Concierge calling specialist`)

- **When:** Concierge has chosen a specialist (e.g. Arista `abc67f38-...`) and is about to send the query.
- **Inspect:** `agent_id` (inventory_id), `question`.

### 2. Message bus routes to the specialist

**File:** `src/agent/message_bus.py`  
**Function:** `_process_messages`  
**Line:** Just before `handler = self.subscribers[message.to_agent]` (comment: `# BREAKPOINT: MessageBus routing query to specialist`)

- **When:** The Concierge’s message has been dequeued and is about to be handed to the specialist’s handler.
- **Inspect:** `message.from_agent` (concierge), `message.to_agent` (e.g. `abc67f38-...`), `message.content`.

### 3. Specialist receives the query

**File:** `src/agent/device_agent.py`  
**Function:** `_handle_message`  
**Line:** Right after the docstring (comment: `# BREAKPOINT: Specialist received query from Concierge`)

- **When:** The specialist (e.g. Arista DUT agent) has received the Concierge’s question.
- **Inspect:** `self.context.device_name`, `message.from_agent`, `message.content`.

### 4. Specialist processes the query (before Gemini)

**File:** `src/agent/device_agent.py`  
**Function:** `_process_query`  
**Line:** Right after the docstring (comment: `# BREAKPOINT: Specialist processing query`)

- **When:** The specialist is about to call Gemini (and possibly tools like `read_device_configuration`).
- **Inspect:** `query`, `self.context.device_name`.

### 5. Specialist sends response back

**File:** `src/agent/device_agent.py`  
**Function:** `_handle_message`  
**Line:** Just before `response = AgentMessage(...)` (comment: `# Specialist sending response`)

- **When:** The specialist has generated `response_text` and is about to wrap it in an `AgentMessage` to the Concierge.
- **Inspect:** `response_text`.

### 6. Concierge receives the response

**File:** `src/agent/concierge_agent.py`  
**Function:** `query_specialist`  
**Line:** Just after `response = loop.run_until_complete(self.message_bus.send_and_wait(...))` (comment: `# BREAKPOINT: Concierge received response from specialist`)

- **When:** The Concierge has received the specialist’s reply and is about to return it to the tool (and then to the user).
- **Inspect:** `response`, `response.content`.

## Flow summary

1. User: “what is the current configuration of the Arista?” at `[Concierge]>`
2. Concierge (Gemini) calls tool `query_specialist(agent_id="abc67f38-8b7e-4bf0-8aa4-8d2cbcc8a0b6", question="What is the current configuration?")`
3. **Breakpoint 1** – `concierge_agent.query_specialist`: Concierge builds and sends message.
4. **Breakpoint 2** – `message_bus._process_messages`: MessageBus delivers to specialist.
5. **Breakpoint 3** – `device_agent._handle_message`: Arista specialist receives query.
6. **Breakpoint 4** – `device_agent._process_query`: Specialist runs Gemini (and tools).
7. **Breakpoint 5** – `device_agent._handle_message`: Specialist builds response message.
8. MessageBus resolves the Concierge’s `send_and_wait` with that response.
9. **Breakpoint 6** – `concierge_agent.query_specialist`: Concierge gets response and returns it to Gemini, which then answers the user.

Use **Step Over** / **Step Into** from breakpoint 1 to follow the full path through the MessageBus and into the Specialist.
