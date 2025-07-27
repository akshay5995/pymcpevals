"""Core evaluation functionality for pymcpevals."""

import asyncio
import json
import time
from typing import Any

import litellm
from fastmcp import Client
from litellm import acompletion

from .types import ConversationTurn, EvaluationCase, EvaluationResult

litellm.modify_params = True


async def _setup_tools_from_server(client: Client) -> list[dict[str, Any]]:
    """Set up formatted tools from the MCP server."""
    tools = await client.list_tools()
    formatted_tools = []

    if tools:
        for tool in tools:
            input_schema = getattr(tool, "input_schema", getattr(tool, "inputSchema", {}))
            formatted_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": input_schema,
                    },
                }
            )

    return formatted_tools


async def _execute_tool_call(
    client: Client,
    tool_call: Any,
    tool_call_details: list[dict[str, Any]],
    tools_used: list[str],
    available_tools: list[str] | None = None,
) -> dict[str, Any]:
    """Execute a single tool call and return the result message."""
    tool_name = tool_call.function.name
    tool_args = json.loads(tool_call.function.arguments)

    # Check if tool exists in available tools
    if available_tools and tool_name not in available_tools:
        # LLM hallucinated a tool that doesn't exist
        tool_call_details.append(
            {
                "tool_name": tool_name,
                "arguments": tool_args,
                "success": False,
                "execution_time_ms": 0,
                "error_message": f"Tool '{tool_name}' does not exist on the server",
                "hallucinated": True,
            }
        )

        return {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": f"Error: Tool '{tool_name}' does not exist on the server",
        }

    # Start timing and ensure we track the time properly
    start_time = time.perf_counter()
    execution_time_ms = 0.0

    try:
        tool_result = await client.call_tool(tool_name, tool_args)
        execution_time_ms = (time.perf_counter() - start_time) * 1000.0

        # Only add to tools_used if the call succeeded
        tools_used.append(tool_name)

        # Format the result
        if hasattr(tool_result, "data"):
            result_text = str(tool_result.data)
        elif hasattr(tool_result, "content"):
            if isinstance(tool_result.content, list):
                result_text = "\n".join(
                    [
                        item.text if hasattr(item, "text") else str(item)
                        for item in tool_result.content
                    ]
                )
            else:
                result_text = str(tool_result.content)
        else:
            result_text = str(tool_result)

        # Record successful tool call
        tool_call_details.append(
            {
                "tool_name": tool_name,
                "arguments": tool_args,
                "success": True,
                "execution_time_ms": execution_time_ms,
                "result_preview": (
                    result_text[:100] + "..." if len(result_text) > 100 else result_text
                ),
            }
        )

        return {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": result_text,
        }

    except Exception as e:
        execution_time_ms = (time.perf_counter() - start_time) * 1000.0

        # Still add to tools_used even if it failed - the tool was attempted
        tools_used.append(tool_name)

        # Record failed tool call
        tool_call_details.append(
            {
                "tool_name": tool_name,
                "arguments": tool_args,
                "success": False,
                "execution_time_ms": execution_time_ms,
                "error_message": str(e),
            }
        )

        return {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": f"Error calling tool: {e!s}",
        }


async def _handle_tool_calls(
    client: Client,
    message: Any,
    messages: list[dict[str, Any]],
    tools_used: list[str],
    tool_call_details: list[dict[str, Any]],
    model: str,
    available_tools: list[str] | None = None,
) -> None:
    """Handle tool calls and get final response."""
    # Convert LiteLLM message to dict for consistency
    messages.append(
        {
            "role": "assistant",
            "content": message.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": tc.type or "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ],
        }
    )

    # Execute each tool call
    for tool_call in message.tool_calls:
        tool_result_message = await _execute_tool_call(
            client, tool_call, tool_call_details, tools_used, available_tools
        )
        messages.append(tool_result_message)

    # Get final response after tool execution
    try:
        final_response = await acompletion(model=model, messages=messages)
        if final_response.choices[0].message.content:
            assistant_content = final_response.choices[0].message.content
            messages.append(
                {
                    "role": "assistant",
                    "content": str(assistant_content),
                }
            )
    except Exception as e:
        # Handle API errors in final response
        error_msg = f"LLM API error in final response: {e!s}"
        messages.append({"role": "assistant", "content": error_msg})


async def run_evals_trajectory(
    client: Client, turns: list[ConversationTurn], model: str = "gpt-4"
) -> tuple[list[dict[str, Any]], list[str], list[dict[str, Any]]]:
    """
    Execute a conversation trajectory with an MCP server.

    Args:
        client: FastMCP client (already connected)
        turns: List of conversation turns to execute
        model: LLM model to use

    Returns:
        Tuple of (conversation_history, tools_used, tool_call_details)
    """
    # Get available tools from the server
    formatted_tools = await _setup_tools_from_server(client)

    # Extract tool names for validation
    available_tool_names = (
        [tool["function"]["name"] for tool in formatted_tools] if formatted_tools else []
    )

    # System prompt for MCP tool usage
    system_prompt = """You are an assistant with access to MCP (Model Context Protocol) tools. 
Use the available tools to help answer the user's questions. Be thorough and provide helpful responses."""

    messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    tools_used: list[str] = []
    tool_call_details: list[dict[str, Any]] = []

    try:
        # Execute each turn in the conversation
        for turn_idx, turn in enumerate(turns):
            if turn.role == "user":
                messages.append({"role": "user", "content": turn.content})

                # Track tools used in this specific turn
                turn_start_tool_count = len(tools_used)

                # Get response from LLM with tools
                try:
                    response = await acompletion(
                        model=model,
                        messages=messages,
                        tools=formatted_tools if formatted_tools else None,
                        tool_choice="auto" if formatted_tools else None,
                    )
                except Exception as e:
                    # Handle rate limits and other API errors gracefully
                    error_msg = f"LLM API error during turn: {e!s}"
                    messages.append({"role": "assistant", "content": error_msg})
                    break  # Exit the turn processing loop

                message = response.choices[0].message

                # Handle tool calls if any
                if message.tool_calls:
                    await _handle_tool_calls(
                        client,
                        message,
                        messages,
                        tools_used,
                        tool_call_details,
                        model,
                        available_tool_names,
                    )
                # No tools called, add direct response
                elif message.content:
                    messages.append({"role": "assistant", "content": str(message.content)})

                # Track which tools were called in this turn
                turn_tools = (
                    tools_used[turn_start_tool_count:]
                    if len(tools_used) > turn_start_tool_count
                    else []
                )

                # Add metadata about expected vs actual tools for this turn
                if turn.expected_tools:
                    messages[-1]["_turn_metadata"] = {
                        "turn_index": turn_idx,
                        "expected_tools": turn.expected_tools,
                        "actual_tools": turn_tools,
                        "tools_match": (
                            set(turn_tools) == set(turn.expected_tools)
                            if turn_tools or turn.expected_tools
                            else True
                        ),
                    }

            elif turn.role == "assistant":
                # For assistant turns, just add to conversation history
                messages.append({"role": "assistant", "content": turn.content})

            elif turn.role == "system":
                # For system turns, add to conversation
                messages.append({"role": "system", "content": turn.content})

        return messages, tools_used, tool_call_details

    except Exception as e:
        error_msg = f"Error during trajectory execution: {e!s}"
        messages.append({"role": "assistant", "content": error_msg})
        return messages, tools_used, tool_call_details


async def run_evals(client: Client, prompt: str, model: str = "gpt-4") -> str:
    """
    Connect to MCP server, get tools, use them to answer the prompt.

    Single-prompt evaluation function.

    Args:
        client: FastMCP client (already connected)
        prompt: User query to answer using the MCP tools
        model: LLM model to use

    Returns:
        The LLM's response after using the MCP tools
    """
    # Check if tools are available first
    tools = await client.list_tools()
    if not tools:
        return "No tools available from the MCP server."

    # Convert single prompt to trajectory format
    turns = [ConversationTurn(role="user", content=prompt)]
    conversation_history, _, _ = await run_evals_trajectory(client, turns, model)

    # Extract the final assistant response
    for message in reversed(conversation_history):
        if message.get("role") == "assistant":
            content = message.get("content", "")
            return str(content) if content is not None else ""

    return "No response generated"


def _check_tool_usage_per_turn(conversation_history: list[dict[str, Any]]) -> list[str]:
    """Check tool usage per turn and return list of issues."""
    tool_usage_issues = []

    for msg in conversation_history:
        turn_metadata = msg.get("_turn_metadata")
        if turn_metadata:
            turn_idx = turn_metadata["turn_index"]
            expected = turn_metadata["expected_tools"]
            actual = turn_metadata["actual_tools"]

            if not turn_metadata["tools_match"]:
                expected_str = f"[{', '.join(sorted(expected))}]" if expected else "[]"
                actual_str = f"[{', '.join(sorted(actual))}]" if actual else "[]"
                tool_usage_issues.append(
                    f"Turn {turn_idx + 1}: Expected {expected_str} but got {actual_str}"
                )

    return tool_usage_issues


def _check_overall_tool_usage(
    turns: list[ConversationTurn], tools_used: list[str]
) -> tuple[str, list[str]]:
    """Check overall tool usage and return expected_tools_check string and issues."""
    expected_tools_check = ""
    tool_usage_issues = []

    if any(turn.expected_tools for turn in turns):
        all_expected_tools = []
        for turn in turns:
            if turn.expected_tools:
                all_expected_tools.extend(turn.expected_tools)

        if all_expected_tools:
            expected_set = set(all_expected_tools)
            used_set = set(tools_used)

            expected_tools_check = f"\nExpected tools: [{', '.join(sorted(expected_set))}]"
            expected_tools_check += (
                f"\nActual tools used: [{', '.join(sorted(used_set)) if tools_used else ''}]"
            )

            # Check if all expected tools were called
            missing_tools = expected_set - used_set
            if missing_tools:
                tool_usage_issues.append(
                    f"Missing expected tools: [{', '.join(sorted(missing_tools))}]"
                )

            # Check for unexpected tools
            unexpected_tools = used_set - expected_set
            if unexpected_tools:
                tool_usage_issues.append(
                    f"Unexpected tools called: [{', '.join(sorted(unexpected_tools))}]"
                )

    return expected_tools_check, tool_usage_issues


def _create_conversation_summary(conversation_history: list[dict[str, Any]]) -> str:
    """Create a server-focused summary of the conversation for evaluation."""
    summary_parts = []
    turn_number = 0

    for i, msg in enumerate(conversation_history):
        if msg.get("role") == "user":
            turn_number += 1
            user_content = msg.get("content", "")

            # Look ahead for assistant response and tool calls
            assistant_response = ""
            tool_calls_info = []

            # Find the corresponding assistant response(s)
            for j in range(i + 1, len(conversation_history)):
                next_msg = conversation_history[j]
                if next_msg.get("role") == "assistant":
                    # Check for tool calls
                    if next_msg.get("tool_calls"):
                        for tc in next_msg["tool_calls"]:
                            tool_name = tc.get("function", {}).get("name", "unknown")
                            tool_calls_info.append(f"Called {tool_name}")

                    # Get final assistant content
                    if next_msg.get("content"):
                        assistant_response = next_msg["content"]
                        break
                elif next_msg.get("role") == "tool":
                    # Capture tool result
                    tool_result = next_msg.get("content", "")[:50]  # First 50 chars
                    tool_calls_info.append(f"→ Result: {tool_result}")
                elif next_msg.get("role") == "user":
                    break  # Next user turn

            # Build turn summary focusing on server capabilities
            turn_summary = f"Turn {turn_number}:\n"
            turn_summary += f"User Request: {user_content}\n"

            if tool_calls_info:
                turn_summary += f"Server Tools: {', '.join(tool_calls_info)}\n"
            else:
                turn_summary += "Server Tools: No tools called\n"

            if assistant_response:
                turn_summary += f"Final Response: {assistant_response}\n"

            summary_parts.append(turn_summary)

    return "\n".join(summary_parts)


async def grade_trajectory(
    model: str,
    conversation_history: list[dict[str, Any]],
    turns: list[ConversationTurn],
    tools_used: list[str],
    tool_call_details: list[dict[str, Any]],
    expected_result: str | None = None,
) -> EvaluationResult:
    """
    Grade how well the MCP server performed across a conversation trajectory.

    Args:
        model: LLM model to use for evaluation
        conversation_history: Full conversation including tool calls
        turns: Original conversation turns with expectations
        tools_used: List of tools that were called
        tool_call_details: Detailed information about tool calls
        expected_result: Optional description of expected behavior

    Returns:
        EvaluationResult with trajectory-specific scores and comments
    """
    # Create conversation summary
    conversation_summary = _create_conversation_summary(conversation_history)

    # Check tool usage per turn
    tool_usage_issues = _check_tool_usage_per_turn(conversation_history)

    # Check overall tool usage
    expected_tools_check, overall_issues = _check_overall_tool_usage(turns, tools_used)
    tool_usage_issues.extend(overall_issues)

    # If there are tool usage issues, automatically fail
    if tool_usage_issues:
        tool_issues_text = "\n".join(tool_usage_issues)

        # Gather all expected tools from turns
        all_expected_tools = []
        for turn in turns:
            if turn.expected_tools:
                all_expected_tools.extend(turn.expected_tools)

        # For tool mismatches, return a failed evaluation immediately
        return EvaluationResult(
            accuracy=1,
            completeness=1,
            relevance=1,
            clarity=1,
            reasoning=1,
            average_score=1.0,
            overall_comments=f"TOOL VALIDATION FAILED:\n{tool_issues_text}",
            conversation_history=conversation_history,
            tools_used=tools_used,
            expected_tools=list(set(all_expected_tools)) if all_expected_tools else None,
            expected_result=expected_result,
            model_used=model,
            server_source="unknown",
            total_execution_time_ms=sum(
                call.get("execution_time_ms", 0) for call in tool_call_details
            ),
            failed_tool_calls=sum(1 for call in tool_call_details if not call.get("success", True)),
            tool_call_details=tool_call_details,
            passed=False,  # Explicitly fail when expected tools aren't used
        )

    eval_prompt = f"""You are evaluating an MCP SERVER'S CAPABILITIES across a multi-turn trajectory, NOT the LLM's conversation style.

IMPORTANT: In tool-calling conversations, it's NORMAL for assistant messages to have empty content during tool execution. Focus on whether the SERVER provided the right tools and correct results.

Conversation Summary:
{conversation_summary}

{expected_tools_check}

{f"Expected Server Outcome: {expected_result}" if expected_result else ""}

Evaluate the SERVER'S performance on these criteria (1-5):

1. **Accuracy** (1-5): Did the server's tools return correct, accurate results?
2. **Completeness** (1-5): Did the server provide all necessary tools to complete the task?
3. **Relevance** (1-5): Were the server's tools relevant to the user's requests?
4. **Clarity** (1-5): Are the server's tool results clear and well-formatted?
5. **Reasoning** (1-5): Did the server enable logical progression through the multi-step task?

Focus ONLY on server capabilities:
- ✅ Tool execution success/failure
- ✅ Correctness of tool results
- ✅ Availability of needed tools
- ✅ Tool chaining across turns
- ❌ IGNORE empty content during tool calls (this is normal)
- ❌ IGNORE LLM conversation patterns

Example: If tools were called successfully and returned correct results, that's a SUCCESS regardless of conversation style.

Provide your evaluation in the following JSON format:
{{
    "accuracy": <score>,
    "completeness": <score>,
    "relevance": <score>,
    "clarity": <score>,
    "reasoning": <score>,
    "overall_comments": "<brief summary focusing on SERVER tool capabilities>"
}}

Only respond with the JSON object, no additional text."""

    try:
        response = await acompletion(
            model=model,
            messages=[{"role": "user", "content": eval_prompt}],
        )

        result_text = response.choices[0].message.content

        # Clean up markdown formatting if present
        if result_text.strip().startswith("```json"):
            # Extract JSON from markdown code block
            lines = result_text.strip().split("\n")
            json_lines = []
            in_json = False
            for line in lines:
                if line.strip() == "```json":
                    in_json = True
                    continue
                if line.strip() == "```" and in_json:
                    break
                if in_json:
                    json_lines.append(line)
            result_text = "\n".join(json_lines)

        evaluation = json.loads(result_text)

        # Calculate average score
        scores = [
            evaluation["accuracy"],
            evaluation["completeness"],
            evaluation["relevance"],
            evaluation["clarity"],
            evaluation["reasoning"],
        ]
        evaluation["average_score"] = sum(scores) / len(scores)

        # Calculate execution time
        total_execution_time = sum(call.get("execution_time_ms", 0) for call in tool_call_details)

        # Count failed tool calls
        failed_tool_calls = sum(1 for call in tool_call_details if not call.get("success", True))

        # Gather all expected tools from turns
        all_expected_tools = []
        for turn in turns:
            if turn.expected_tools:
                all_expected_tools.extend(turn.expected_tools)

        result = EvaluationResult(
            **evaluation,
            conversation_history=conversation_history,
            tools_used=tools_used,
            expected_tools=list(set(all_expected_tools)) if all_expected_tools else None,
            expected_result=expected_result,
            model_used=model,
            server_source="unknown",  # Will be set by caller
            total_execution_time_ms=total_execution_time,
            failed_tool_calls=failed_tool_calls,
            tool_call_details=tool_call_details,
        )
        # Set passed based on default threshold
        result.passed = result.average_score >= 3.0
        return result

    except json.JSONDecodeError as e:
        return EvaluationResult(
            accuracy=1,
            completeness=1,
            relevance=1,
            clarity=1,
            reasoning=1,
            average_score=1.0,
            overall_comments=f"Failed to parse evaluation response: {e!s}",
            conversation_history=conversation_history,
            tools_used=tools_used,
            expected_result=expected_result,
            model_used=model,
            server_source="unknown",
        )
    except Exception as e:
        return EvaluationResult(
            accuracy=1,
            completeness=1,
            relevance=1,
            clarity=1,
            reasoning=1,
            average_score=1.0,
            overall_comments=f"Evaluation failed: {e!s}",
            conversation_history=conversation_history,
            tools_used=tools_used,
            expected_result=expected_result,
            model_used=model,
            server_source="unknown",
            error=str(e),
        )


async def grade(
    model: str,
    prompt: str,
    server_response: str,
    expected_result: str | None = None,
    expected_tools: list[str] | None = None,
    tools_used: list[str] | None = None,
) -> EvaluationResult:
    """
    Grade how well the MCP server answered the prompt.

    Single-prompt evaluation grading function.

    Args:
        model: LLM model to use for evaluation
        prompt: Original user prompt
        server_response: Response from the MCP server
        expected_result: Optional description of expected behavior
        expected_tools: Optional list of tools expected to be called
        tools_used: Optional list of tools that were called

    Returns:
        EvaluationResult with scores and comments
    """
    # Build tool usage info for the prompt
    tool_info = ""
    if expected_tools or tools_used:
        tool_info = "\n\nTool Usage:"
        if expected_tools:
            tool_info += f"\nExpected tools: {', '.join(expected_tools)}"
        if tools_used is not None:
            tool_info += f"\nActual tools used: {', '.join(tools_used) if tools_used else 'None'}"

    eval_prompt = f"""You are evaluating an MCP SERVER'S CAPABILITIES, NOT the LLM's response quality.

User's Question: {prompt}

MCP Server's Final Response: {server_response}
{tool_info}

{f"Expected Server Outcome: {expected_result}" if expected_result else ""}

Evaluate the SERVER'S performance on these criteria (1-5):

1. **Accuracy** (1-5): Did the server's tools provide accurate, correct information?
2. **Completeness** (1-5): Did the server provide all necessary tools to address the question?
3. **Relevance** (1-5): Were the server's tools and results relevant to the user's request?
4. **Clarity** (1-5): Are the server's tool results clear and well-formatted?
5. **Reasoning** (1-5): Did the server's tools enable logical problem-solving?

Focus ONLY on server capabilities:
- ✅ Tool execution success/failure
- ✅ Correctness of tool results
- ✅ Availability of needed tools
- ✅ Tool result formatting and clarity
- ❌ IGNORE LLM response style and formatting
- ❌ IGNORE how the LLM chose to present information

{
"IMPORTANT: If expected tools were called successfully and returned correct results, that's a SUCCESS regardless of LLM presentation style."
if expected_tools else ""
}

Provide your evaluation in the following JSON format:
{{
    "accuracy": <score>,
    "completeness": <score>,
    "relevance": <score>,
    "clarity": <score>,
    "reasoning": <score>,
    "overall_comments": "<brief summary focusing on SERVER tool capabilities>"
}}

Only respond with the JSON object, no additional text."""

    try:
        response = await acompletion(
            model=model,
            messages=[{"role": "user", "content": eval_prompt}],
        )

        result_text = response.choices[0].message.content

        # Clean up markdown formatting if present
        if result_text.strip().startswith("```json"):
            # Extract JSON from markdown code block
            lines = result_text.strip().split("\n")
            json_lines = []
            in_json = False
            for line in lines:
                if line.strip() == "```json":
                    in_json = True
                    continue
                if line.strip() == "```" and in_json:
                    break
                if in_json:
                    json_lines.append(line)
            result_text = "\n".join(json_lines)

        evaluation = json.loads(result_text)

        # Calculate average score
        scores = [
            evaluation["accuracy"],
            evaluation["completeness"],
            evaluation["relevance"],
            evaluation["clarity"],
            evaluation["reasoning"],
        ]
        evaluation["average_score"] = sum(scores) / len(scores)

        result = EvaluationResult(
            **evaluation,
            prompt=prompt,
            server_response=server_response,
            expected_result=expected_result,
            model_used=model,
            server_source="unknown",  # Will be set by caller
        )
        # Set passed based on default threshold
        result.passed = result.average_score >= 3.0
        return result

    except json.JSONDecodeError as e:
        return EvaluationResult(
            accuracy=1,
            completeness=1,
            relevance=1,
            clarity=1,
            reasoning=1,
            average_score=1.0,
            overall_comments=f"Failed to parse evaluation response: {e!s}",
            prompt=prompt,
            server_response=server_response,
            expected_result=expected_result,
            model_used=model,
            server_source="unknown",
        )
    except Exception as e:
        return EvaluationResult(
            accuracy=1,
            completeness=1,
            relevance=1,
            clarity=1,
            reasoning=1,
            average_score=1.0,
            overall_comments=f"Evaluation failed: {e!s}",
            prompt=prompt,
            server_response=server_response,
            expected_result=expected_result,
            model_used=model,
            server_source="unknown",
            error=str(e),
        )


def grade_sync(
    model: str,
    prompt: str,
    server_response: str,
    expected_result: str | None = None,
) -> EvaluationResult:
    """Synchronous wrapper for the grade function."""
    return asyncio.run(grade(model, prompt, server_response, expected_result))


async def evaluate_mcp_server_trajectory(
    server_source: Any,
    turns: list[ConversationTurn],
    model: str = "gpt-4",
    expected_result: str | None = None,
) -> EvaluationResult:
    """
    Evaluate a multi-turn conversation trajectory with an MCP server.

    Args:
        server_source: Server source for FastMCP client
        turns: List of conversation turns to execute
        model: LLM model to use
        expected_result: Optional description of expected behavior

    Returns:
        Evaluation results with tool call details
    """
    try:
        # Create FastMCP client
        # Handle server config dict format
        if isinstance(server_source, dict):
            # If it's a config dict, extract the command or URL
            if "command" in server_source:
                from .types import ServerConfig

                config = ServerConfig(**server_source)
                server_source = config.get_server_source()
            elif "url" in server_source:
                server_source = server_source["url"]

        client = Client(server_source)

        async with client:
            # Run the trajectory evaluation
            conversation_history, tools_used, tool_call_details = await run_evals_trajectory(
                client, turns, model
            )

            # Get basic evaluation
            evaluation = await grade_trajectory(
                model, conversation_history, turns, tools_used, tool_call_details, expected_result
            )
            evaluation.server_source = str(server_source)
            return evaluation

    except Exception as e:
        error_message = f"Server connection/trajectory evaluation failed: {e!s}"
        if "Could not infer a valid transport" in str(e):
            error_message += f" (server_source: {server_source})"

        return EvaluationResult(
            accuracy=1,
            completeness=1,
            relevance=1,
            clarity=1,
            reasoning=1,
            average_score=1.0,
            overall_comments=error_message,
            passed=False,
            expected_result=expected_result,
            model_used=model,
            server_source=str(server_source),
            error=str(e),
        )


async def evaluate_mcp_server(
    server_source: Any,
    prompt: str,
    model: str = "gpt-4",
    expected_result: str | None = None,
    expected_tools: list[str] | None = None,
) -> EvaluationResult:
    """
    Evaluate a single-turn prompt with an MCP server.

    Args:
        server_source: Server source for FastMCP client
        prompt: User prompt to evaluate
        model: LLM model to use
        expected_result: Optional description of expected behavior
        expected_tools: Optional list of tools expected to be called

    Returns:
        Evaluation results with tool call details
    """
    try:
        # Create FastMCP client
        # Handle server config dict format
        if isinstance(server_source, dict):
            # If it's a config dict, extract the command or URL
            if "command" in server_source:
                from .types import ServerConfig

                config = ServerConfig(**server_source)
                server_source = config.get_server_source()
            elif "url" in server_source:
                server_source = server_source["url"]

        client = Client(server_source)

        async with client:
            # Convert single prompt to trajectory format with expected_tools
            turns = [ConversationTurn(role="user", content=prompt, expected_tools=expected_tools)]

            # Run the evaluation
            conversation_history, tools_used, tool_call_details = await run_evals_trajectory(
                client, turns, model
            )

            # Check if expected tools were called for single-turn
            if expected_tools:
                missing_tools = set(expected_tools) - set(tools_used)
                unexpected_tools = set(tools_used) - set(expected_tools)

                if missing_tools or unexpected_tools:
                    error_parts = []
                    if missing_tools:
                        error_parts.append(
                            f"Missing expected tools: {', '.join(sorted(missing_tools))}"
                        )
                    if unexpected_tools:
                        error_parts.append(
                            f"Unexpected tools called: {', '.join(sorted(unexpected_tools))}"
                        )

                    # Return failed evaluation for tool mismatch
                    return EvaluationResult(
                        accuracy=1,
                        completeness=1,
                        relevance=1,
                        clarity=1,
                        reasoning=1,
                        average_score=1.0,
                        overall_comments=f"TOOL VALIDATION FAILED:\n{'; '.join(error_parts)}",
                        passed=False,
                        prompt=prompt,
                        server_response=(
                            conversation_history[-1].get("content", "")
                            if conversation_history
                            else ""
                        ),
                        expected_result=expected_result,
                        expected_tools=expected_tools,
                        model_used=model,
                        server_source=str(server_source),
                        tools_used=tools_used,
                        conversation_history=conversation_history,
                        tool_call_details=tool_call_details,
                        total_execution_time_ms=sum(
                            call.get("execution_time_ms", 0) for call in tool_call_details
                        ),
                        failed_tool_calls=sum(
                            1 for call in tool_call_details if not call.get("success", True)
                        ),
                    )

            # Get basic evaluation
            evaluation = await grade(
                model,
                prompt,
                conversation_history[-1].get("content", "") if conversation_history else "",
                expected_result,
                expected_tools,
                tools_used,
            )

            # Add tool call details to single-turn evaluation
            evaluation.tools_used = tools_used
            evaluation.expected_tools = expected_tools
            evaluation.conversation_history = conversation_history
            evaluation.tool_call_details = tool_call_details
            evaluation.total_execution_time_ms = sum(
                call.get("execution_time_ms", 0) for call in tool_call_details
            )
            evaluation.failed_tool_calls = sum(
                1 for call in tool_call_details if not call.get("success", True)
            )
            evaluation.server_source = str(server_source)

            return evaluation

    except Exception as e:
        error_message = f"Server connection/evaluation failed: {e!s}"
        if "Could not infer a valid transport" in str(e):
            error_message += f" (server_source: {server_source})"

        return EvaluationResult(
            accuracy=1,
            completeness=1,
            relevance=1,
            clarity=1,
            reasoning=1,
            average_score=1.0,
            overall_comments=error_message,
            passed=False,
            prompt=prompt,
            server_response="",
            expected_result=expected_result,
            model_used=model,
            server_source=str(server_source),
            error=str(e),
        )


async def evaluate_case(
    server_source: Any,
    case: "EvaluationCase",
    model: str = "gpt-4",
) -> EvaluationResult:
    """
    Evaluate a single EvaluationCase (supports both single-prompt and trajectory modes).

    Args:
        server_source: Server source for FastMCP client
        case: EvaluationCase to evaluate
        model: LLM model to use

    Returns:
        Evaluation results
    """
    if case.is_trajectory and case.turns:
        return await evaluate_mcp_server_trajectory(
            server_source, case.turns, model, case.expected_result
        )
    if case.prompt:
        return await evaluate_mcp_server(
            server_source, case.prompt, model, case.expected_result, case.expected_tools
        )
    raise ValueError("EvaluationCase must have either prompt or turns")
