"""POC Test 1: openai 包 + 百炼 DashScope 跑 tool use 循环"""
import json
import os
import sys
import time
from openai import OpenAI

client = OpenAI(
    api_key="sk-7232450f93ce438096c1984ce9eb0823",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

MODEL = "qwen3.6-plus"

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_drug_price",
            "description": "查询药品单价",
            "parameters": {
                "type": "object",
                "properties": {
                    "drug_name": {"type": "string", "description": "药品通用名"}
                },
                "required": ["drug_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_coverage_amount",
            "description": "查询保单剩余保额",
            "parameters": {
                "type": "object",
                "properties": {
                    "policy_id": {"type": "string", "description": "保单号"}
                },
                "required": ["policy_id"],
            },
        },
    },
]


def execute_tool(tool_name, args):
    """模拟工具本地执行"""
    if tool_name == "get_drug_price":
        prices = {"来那度胺": 1280, "硼替佐米": 3500, "伊布替尼": 4860}
        return json.dumps({"price_per_unit": prices.get(args["drug_name"], 0)}, ensure_ascii=False)
    elif tool_name == "get_coverage_amount":
        return json.dumps({"policy_id": args["policy_id"], "remaining": 50000}, ensure_ascii=False)
    return json.dumps({"error": "unknown tool"})


def test():
    sys.stderr.write("[Test  1] Tool use loop...\n")

    messages = [{
        "role": "user",
        "content": "查一下来那度胺的价格，保单 P001 还剩多少保额。"
    }]
    tool_calls_made = 0

    for turn in range(5):  # 最多 5 轮
        resp = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            temperature=0.1,
        )
        msg = resp.choices[0].message

        if msg.tool_calls is None:
            # 没有工具调用 — 模型给出了最终回复
            sys.stderr.write(f"[Test  1] OK — {turn+1} turns, {tool_calls_made} tool calls, 模型回复: {msg.content[:60]}...\n")
            return True, turn + 1, tool_calls_made

        # 添加 assistant 消息
        messages.append({
            "role": "assistant",
            "content": msg.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ],
        })

        # 执行每个工具调用
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)
            result = execute_tool(tc.function.name, args)
            tool_calls_made += 1
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })
    else:
        sys.stderr.write("[Test  1] FAIL — loop exhausted without final response\n")
        return False, 5, tool_calls_made


if __name__ == "__main__":
    ok, turns, calls = test()
    print(f"TEST1: tool_use_loop {'PASS' if ok else 'FAIL'} turns={turns} calls={calls}")
    sys.exit(0 if ok else 1)
