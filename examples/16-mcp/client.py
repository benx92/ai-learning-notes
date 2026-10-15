"""不调用模型，直接检查 MCP 服务的工具、资源和提示模板。"""

import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from pydantic import AnyUrl


async def inspect_server(session):
    info = await session.initialize()
    print("协议版本：", info.protocolVersion)
    tools = await session.list_tools()
    print("工具：", [tool.name for tool in tools.tools])
    print("参数要求：", tools.tools[0].inputSchema)

    resources = await session.list_resources()
    print("资源：", [str(resource.uri) for resource in resources.resources])
    templates = await session.list_resource_templates()
    print("资源模板：", [template.uriTemplate for template in templates.resourceTemplates])
    for uri in ("policy://refund/overview", "policy://refund/customer/member"):
        result = await session.read_resource(AnyUrl(uri))
        for block in result.contents:
            if isinstance(block, types.TextResourceContents):
                print("政策：", block.text)

    prompts = await session.list_prompts()
    print("提示模板：", [prompt.name for prompt in prompts.prompts])
    prompt = await session.get_prompt("explain_refund", arguments={"order_id": "A1001"})
    for message in prompt.messages:
        if isinstance(message.content, types.TextContent):
            print("任务说明：", message.content.text)

    for order_id in ("A1001", "A2002", "bad-id"):
        result = await session.call_tool("get_refund_status", arguments={"order_id": order_id})
        print("查询：", order_id, "工具执行出错：", bool(result.isError))
        for block in result.content:
            if isinstance(block, types.TextContent):
                print("结果：", block.text)


async def main():
    server_path = Path(__file__).with_name("server.py").resolve()
    params = StdioServerParameters(command=sys.executable, args=[str(server_path)])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await inspect_server(session)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
