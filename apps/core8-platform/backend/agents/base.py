from dataclasses import dataclass
from typing import Callable, Awaitable
import anthropic
from config import cfg
from tools.registry import registry
from security.log_redact import redact
from security.approval import is_blocklisted, needs_approval
import json
import logging

logger = logging.getLogger("core8.agent")


@dataclass
class AgentConfig:
    id: str
    name: str
    description: str
    model: str
    system_prompt: str
    allowed_tools: list[str] | None = None  # None = all tools; list = scoped subset


class BaseAgent:
    def __init__(self, config: AgentConfig):
        self.config = config
        self._client = anthropic.AsyncAnthropic(api_key=cfg.anthropic_api_key)

    async def run(
        self,
        messages: list[dict],
        on_event=None,
        approval_gate: Callable[[str, dict], Awaitable[bool]] | None = None,
        system_context: str | None = None,
    ) -> tuple[str, str]:
        history = list(messages)
        system = self.config.system_prompt
        if system_context:
            system = f"{system}\n\n{system_context}"
        tools = registry.get_schemas(self.config.allowed_tools)

        while True:
            params = {
                "model": self.config.model,
                "max_tokens": 4096,
                "system": system,
                "messages": history,
            }
            if tools:
                params["tools"] = tools

            full_text = ""
            tool_uses = []

            async with self._client.messages.stream(**params) as stream:
                async for event in stream:
                    if hasattr(event, "type"):
                        if event.type == "content_block_delta":
                            delta = event.delta
                            if hasattr(delta, "text"):
                                full_text += delta.text
                                if on_event:
                                    await on_event({"type": "text_delta", "text": delta.text})
                        elif event.type == "content_block_start":
                            block = event.content_block
                            if block.type == "tool_use":
                                tool_uses.append({
                                    "id": block.id,
                                    "name": block.name,
                                    "input": {},
                                })
                        elif event.type == "content_block_stop":
                            pass

                response = await stream.get_final_message()

            # Build assistant content blocks
            assistant_content = []
            if full_text:
                assistant_content.append({"type": "text", "text": full_text})

            # Collect complete tool_use blocks from response
            actual_tool_uses = [b for b in response.content if b.type == "tool_use"]
            for tu in actual_tool_uses:
                assistant_content.append({
                    "type": "tool_use",
                    "id": tu.id,
                    "name": tu.name,
                    "input": tu.input,
                })

            history.append({"role": "assistant", "content": assistant_content})

            if response.stop_reason == "end_turn" or not actual_tool_uses:
                break

            # Execute tools
            tool_results = []
            for tu in actual_tool_uses:
                # Hardline blocklist — never runs
                if is_blocklisted(tu.name):
                    logger.warning("Tool %s is blocklisted — refusing", tu.name)
                    if on_event:
                        await on_event({"type": "tool_blocked", "name": tu.name})
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tu.id,
                        "content": f"Tool '{tu.name}' is blocked by security policy.",
                        "is_error": True,
                    })
                    continue

                # Approval gate
                if needs_approval(tu.name) and approval_gate is not None:
                    if on_event:
                        await on_event({"type": "tool_call", "name": tu.name, "input": tu.input})
                    approved = await approval_gate(tu.name, tu.input)
                    if not approved:
                        logger.info("Tool %s denied by operator", tu.name)
                        if on_event:
                            await on_event({"type": "tool_denied", "name": tu.name})
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tu.id,
                            "content": f"Tool '{tu.name}' was denied by the operator.",
                            "is_error": True,
                        })
                        continue
                else:
                    if on_event:
                        await on_event({"type": "tool_call", "name": tu.name, "input": tu.input})

                result = await registry.dispatch(tu.name, tu.input)
                redacted = redact(json.dumps(result) if not isinstance(result, str) else result)
                logger.info("Tool %s result: %s", tu.name, redacted)
                if on_event:
                    await on_event({"type": "tool_result", "name": tu.name, "result": result})
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": json.dumps(result) if not isinstance(result, str) else result,
                })

            history.append({"role": "user", "content": tool_results})

        if on_event:
            await on_event({"type": "done", "text": full_text})

        return full_text, response.stop_reason
