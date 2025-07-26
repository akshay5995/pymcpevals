"""Core evaluation functionality for pymcpevals."""

import asyncio
import json
from typing import Any

from fastmcp import Client
from litellm import acompletion

from .timing import measure_time
from .types import ConversationTurn, EvaluationCase, EvaluationResult


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
    tool_call,
    tool_call_details: list[dict[str, Any]],
    tools_used: list[str],
) -> dict[str, Any]:
    """Execute a single tool call and return the result message."""
    tool_name = tool_call.function.name
    tools_used.append(tool_name)
    tool_args = json.loads(tool_call.function.arguments)

    try:
        # Measure tool execution time
        with measure_time() as timer:
            tool_result = await client.call_tool(tool_name, tool_args)

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
                "execution_time_ms": timer.elapsed_ms,
                "result_preview": (
                    result_text[:100] + "..."
                    if len(result_text) > 100
                    else result_text
                ),
            }
        )

        return {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": result_text,
        }

    except Exception as e:
        # Record failed tool call
        tool_call_details.append(
            {
                "tool_name": tool_name,
                "arguments": tool_args,
                "success": False,
                "execution_time_ms": timer.elapsed_ms,
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
    message,
    messages: list[dict[str, Any]],
    tools_used: list[str],
    tool_call_details: list[dict[str, Any]],
    model: str,
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
            client, tool_call, tool_call_details, tools_used
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

    # System prompt for MCP tool usage
    system_prompt = """You are an assistant with access to MCP (Model Context Protocol) tools. 
Use the available tools to help answer the user's questions. Be thorough and provide helpful responses."""

    messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    tools_used = []
    tool_call_details = []

    try:
        # Execute each turn in the conversation
        for turn in turns:
            if turn.role == "user":
                messages.append({"role": "user", "content": turn.content})

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
                        client, message, messages, tools_used, tool_call_details, model
                    )
                # No tools called, add direct response
                elif message.content:
                    messages.append({"role": "assistant", "content": str(message.content)})

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
    # Create a summary of the conversation for evaluation
    user_inputs = []
    assistant_responses = []

    for msg in conversation_history:
        if msg.get("role") == "user":
            user_inputs.append(msg.get("content", ""))
        elif msg.get("role") == "assistant":
            assistant_responses.append(msg.get("content", ""))

    conversation_summary = ""
    for i, (user_msg, assistant_msg) in enumerate(
        zip(user_inputs, assistant_responses, strict=False)
    ):
        conversation_summary += f"Turn {i + 1}:\nUser: {user_msg}\nAssistant: {assistant_msg}\n\n"

    # Check if expected tools were used
    expected_tools_check = ""
    if any(turn.expected_tools for turn in turns):
        all_expected_tools = []
        for turn in turns:
            if turn.expected_tools:
                all_expected_tools.extend(turn.expected_tools)

        if all_expected_tools:
            expected_tools_check = f"\nExpected tools: {', '.join(set(all_expected_tools))}"
            expected_tools_check += (
                f"\nActual tools used: {', '.join(tools_used) if tools_used else 'None'}"
            )

    eval_prompt = f"""You are evaluating how well an MCP server performed across a multi-turn conversation trajectory.

Conversation Summary:
{conversation_summary}

{expected_tools_check}

{f"Expected Outcome: {expected_result}" if expected_result else ""}

Please evaluate the server's performance on the following criteria, scoring each from 1-5:

1. **Accuracy** (1-5): How accurate was the information provided across all turns?
2. **Completeness** (1-5): Did the server fully address all user requests in the conversation?
3. **Relevance** (1-5): Were the responses relevant to the conversation flow?
4. **Clarity** (1-5): Were the responses clear and easy to understand throughout?
5. **Reasoning** (1-5): Did the server show good reasoning and appropriate tool usage?

Consider:
- Tool usage appropriateness and effectiveness
- Conversation flow and coherence
- Achievement of the overall objective
- Handling of multi-step scenarios

Provide your evaluation in the following JSON format:
{{
    "accuracy": <score>,
    "completeness": <score>,
    "relevance": <score>,
    "clarity": <score>,
    "reasoning": <score>,
    "overall_comments": "<brief summary of strengths and weaknesses>"
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

        result = EvaluationResult(
            **evaluation,
            conversation_history=conversation_history,
            tools_used=tools_used,
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
) -> EvaluationResult:
    """
    Grade how well the MCP server answered the prompt.

    Single-prompt evaluation grading function.

    Args:
        model: LLM model to use for evaluation
        prompt: Original user prompt
        server_response: Response from the MCP server
        expected_result: Optional description of expected behavior

    Returns:
        EvaluationResult with scores and comments
    """
    eval_prompt = f"""You are evaluating how well an MCP server answered a user's question.

User's Question: {prompt}

MCP Server's Response: {server_response}

Please evaluate the server's response on the following criteria, scoring each from 1-5:

1. **Accuracy** (1-5): How accurate is the information provided?
2. **Completeness** (1-5): Does the response fully address the user's question?
3. **Relevance** (1-5): Is the response relevant to what was asked?
4. **Clarity** (1-5): Is the response clear and easy to understand?
5. **Reasoning** (1-5): Does the response show good reasoning and logic?

Provide your evaluation in the following JSON format:
{{
    "accuracy": <score>,
    "completeness": <score>,
    "relevance": <score>,
    "clarity": <score>,
    "reasoning": <score>,
    "overall_comments": "<brief summary of strengths and weaknesses>"
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
) -> EvaluationResult:
    """
    Evaluate a single-turn prompt with an MCP server.

    Args:
        server_source: Server source for FastMCP client
        prompt: User prompt to evaluate
        model: LLM model to use
        expected_result: Optional description of expected behavior

    Returns:
        Evaluation results with tool call details
    """
    try:
        # Create FastMCP client
        client = Client(server_source)

        async with client:
            # Convert single prompt to trajectory format
            turns = [ConversationTurn(role="user", content=prompt)]

            # Run the evaluation
            conversation_history, tools_used, tool_call_details = await run_evals_trajectory(
                client, turns, model
            )

            # Get basic evaluation
            evaluation = await grade(
                model,
                prompt,
                conversation_history[-1].get("content", "") if conversation_history else "",
                expected_result,
            )

            # Add tool call details to single-turn evaluation
            evaluation.tools_used = tools_used
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
        return await evaluate_mcp_server(server_source, case.prompt, model, case.expected_result)
    raise ValueError("EvaluationCase must have either prompt or turns")
