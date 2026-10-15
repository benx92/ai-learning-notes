import asyncio
import json
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client
from pydantic import AnyUrl

from bridge_demo import execute_model_call, to_model_tools

SERVER = Path(__file__).with_name("server.py").resolve()


def tool_text(result):
    return "\n".join(block.text for block in result.content if isinstance(block, types.TextContent))


def stdio_case(method):
    async def run(self):
        params = StdioServerParameters(command=sys.executable, args=[str(SERVER)])
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                self.session = session
                self.info = await session.initialize()
                await method(self)
    return run


class StdioProtocolTests(unittest.IsolatedAsyncioTestCase):
    @stdio_case
    async def test_discovery_and_argument_schema(self):
        self.assertEqual(self.info.protocolVersion, "2025-11-25")
        tools = (await self.session.list_tools()).tools
        self.assertEqual([tool.name for tool in tools], ["get_refund_status"])
        self.assertEqual(tools[0].inputSchema["required"], ["order_id"])

    @stdio_case
    async def test_resource_and_template_are_readable(self):
        resources = (await self.session.list_resources()).resources
        self.assertEqual([str(resource.uri) for resource in resources], ["policy://refund/overview"])
        templates = (await self.session.list_resource_templates()).resourceTemplates
        self.assertEqual(templates[0].uriTemplate, "policy://refund/customer/{customer_type}")
        result = await self.session.read_resource(AnyUrl("policy://refund/customer/ordinary"))
        self.assertIn("7日", result.contents[0].text)
        self.assertNotIn("15日", result.contents[0].text)

    @stdio_case
    async def test_prompt_returns_instructions_without_querying(self):
        prompts = (await self.session.list_prompts()).prompts
        self.assertEqual([prompt.name for prompt in prompts], ["explain_refund"])
        result = await self.session.get_prompt("explain_refund", arguments={"order_id": "A1001"})
        text = result.messages[0].content.text
        self.assertIn("A1001", text)
        self.assertIn("先读取", text)
        self.assertNotIn("审核中", text)

    @stdio_case
    async def test_success_and_denied_record(self):
        result = await self.session.call_tool("get_refund_status", {"order_id": "A1001"})
        self.assertFalse(result.isError)
        self.assertEqual(json.loads(tool_text(result))["refund_status"], "审核中")
        denied = await self.session.call_tool("get_refund_status", {"order_id": "A2002"})
        self.assertFalse(denied.isError)
        self.assertEqual(json.loads(tool_text(denied)), {"ok": False, "error": "not_found_or_forbidden"})

    @stdio_case
    async def test_missing_and_invalid_arguments_are_tool_errors(self):
        for arguments in ({}, {"order_id": "bad-id"}):
            with self.subTest(arguments=arguments):
                result = await self.session.call_tool("get_refund_status", arguments)
                self.assertTrue(result.isError)

    @stdio_case
    async def test_bridge_preserves_call_id_and_result(self):
        tools = (await self.session.list_tools()).tools
        mapped = to_model_tools(tools)
        self.assertEqual(mapped[0]["function"]["parameters"], tools[0].inputSchema)
        call = {"id": "call_test", "function": {
            "name": "get_refund_status", "arguments": '{"order_id":"A1001"}'}}
        result = await execute_model_call(self.session, call, {"get_refund_status"})
        self.assertEqual(result["tool_call_id"], "call_test")
        self.assertFalse(json.loads(result["content"])["tool_execution_error"])
        self.assertIn("审核中", result["content"])

    @stdio_case
    async def test_bridge_rejects_unknown_tool_and_bad_json(self):
        for name, arguments in (("submit_refund", "{}"), ("get_refund_status", "{")):
            result = await execute_model_call(self.session, {"id": "call_bad", "function": {
                "name": name, "arguments": arguments}}, {"get_refund_status"})
            self.assertEqual(result["tool_call_id"], "call_bad")
            self.assertTrue(json.loads(result["content"])["tool_execution_error"])


class HttpProtocolTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        with socket.socket() as check:
            check.bind(("127.0.0.1", 8765))
        cls.log = tempfile.TemporaryFile()
        cls.process = subprocess.Popen(
            [sys.executable, str(SERVER), "--transport", "streamable-http"],
            stdout=cls.log, stderr=cls.log,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if cls.process.poll() is not None:
                    raise RuntimeError("HTTP server stopped before becoming ready")
                try:
                    with socket.create_connection(("127.0.0.1", 8765), timeout=0.2):
                        return
                except OSError:
                    time.sleep(0.1)
            raise TimeoutError("HTTP server did not become ready")
        except BaseException:
            cls.process.terminate()
            cls.process.wait(timeout=5)
            cls.log.close()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate()
        cls.process.wait(timeout=5)
        cls.log.close()

    async def test_http_supports_same_tool_resource_and_prompt(self):
        async with streamable_http_client("http://127.0.0.1:8765/mcp") as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                self.assertEqual((await session.list_tools()).tools[0].name, "get_refund_status")
                result = await session.call_tool("get_refund_status", {"order_id": "A1001"})
                self.assertEqual(json.loads(tool_text(result))["refund_status"], "审核中")
                resource = await session.read_resource(AnyUrl("policy://refund/customer/member"))
                self.assertIn("15日", resource.contents[0].text)
                prompt = await session.get_prompt("explain_refund", {"order_id": "A1001"})
                self.assertIn("A1001", prompt.messages[0].content.text)


if __name__ == "__main__":
    unittest.main()
