"""把 MCP 工具说明转成聊天接口格式；用固定请求检查结果回填，不调用模型。"""

import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client


def to_model_tools(tools):
    return [{"type": "function", "function": {
        "name": tool.name, "description": tool.description or "",
        "parameters": tool.inputSchema,
    }} for tool in tools]


async def execute_model_call(session, call, allowed_names):
    function = call["function"]
    name = function["name"]
    try:
        if name not in allowed_names:
            raise ValueError("工具不在允许列表中")
        arguments = json.loads(function["arguments"])
        if not isinstance(arguments, dict):
            raise ValueError("工具参数必须是对象")
        result = await session.call_tool(name, arguments=arguments)
        text = "\n".join(block.text for block in result.content
                         if isinstance(block, types.TextContent))
        payload = {"tool_execution_error": bool(result.isError), "text": text}
    except (ValueError, TypeError) as error:
        payload = {"tool_execution_error": True, "text": str(error)}
    return {"role": "tool", "tool_call_id": call["id"],
            "content": json.dumps(payload, ensure_ascii=False)}


async def main():
    params = StdioServerParameters(command=sys.executable,
                                   args=[str(Path(__file__).with_name("server.py").resolve())])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
            allowed = {tool.name for tool in tools}
            print("可交给模型的工具：", json.dumps(to_model_tools(tools), ensure_ascii=False))
            # 固定请求替代模型输出，仅检查转换和转发；不是在线模型实测。
            message = {"role": "assistant", "content": None, "tool_calls": [{
                "id": "call_demo_1", "type": "function", "function": {
                    "name": "get_refund_status", "arguments": '{"order_id":"A1001"}'}}]}
            history = [message]
            for call in message["tool_calls"]:
                history.append(await execute_model_call(session, call, allowed))
            print("回填历史：", json.dumps(history, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
