#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GLM → MinerU 适配代理 v2
让 GLM-4.6V 输出 MinerU 期望的格式，使 vlm-http-client 能正常工作。

关键点：
- MinerU 布局检测期望: <|box_start|>X1 Y1 X2 Y2<|box_end|><|ref_start|>TYPE<|ref_end|>CONTENT
- MinerU 表格识别期望: OTSL 格式（<fcel>/<ecel>/<nl> 等）
- MinerU 公式识别期望: LaTeX
- MinerU 文本识别期望: 纯文本

代理识别 MinerU 的任务类型（根据 prompt 关键词），注入对应格式指令。

用法: python glm_mineru_proxy.py
"""
import os, sys, json, urllib.request, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GLM_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
MODEL = os.environ.get("GLM_MODEL", "glm-4.6v-flashx")
from dtmd import config as _cfg

PORT = _cfg.PROXY_PORT  # 单一事实源（dtmd.config.PROXY_PORT，读 DTM_PROXY_PORT）
LOG_PATH = os.environ.get("GLM_PROXY_LOG", "")

# 全局限流：限制同时访问 GLM 的请求数，避免 429
GLM_MAX_CONCURRENT = int(os.environ.get("GLM_MAX_CONCURRENT", "1"))
_glm_semaphore = threading.Semaphore(GLM_MAX_CONCURRENT)
_last_request_time = 0.0
_rate_lock = threading.Lock()
MIN_REQUEST_INTERVAL = float(os.environ.get("GLM_MIN_INTERVAL", "0.5"))  # 秒

# MinerU 任务类型 → 让 GLM 按对应格式输出
TASK_INSTRUCTIONS = {
    "layout": """Layout Detection:

You are an expert document layout analyzer. Analyze the document page image and output the layout in EXACTLY this format, one block per line:

<|box_start|>X1 Y1 X2 Y2<|box_end|><|ref_start|>TYPE<|ref_end|>CONTENT

Rules:
- Coordinates are in range 0-1000 (thousandths of page width/height), top-left is (0,0)
- X1 Y1 X2 Y2 = bounding box top-left and bottom-right
- TYPE must be one of: title, text, table, image, equation, list, header, footer, page_number, figure, figure_caption, table_caption
- CONTENT is the text content (empty for image/table/equation types)
- Output ONLY the layout lines, no explanation, no markdown code blocks
- One block per line""",
    "table": """Table Recognition:

Extract the table from the image and output it in EXACTLY this OTSL format (no explanation):

<fcel>CELL_TEXT<ecel><nl><fcel>CELL_TEXT<ecel>...<nl>

Rules:
- <fcel> = first cell in a row, <ecel> = subsequent cell, <nl> = new row
- For merged cells use: <lcel> (horizontal merge), <ucel> (vertical merge)
- Output ONLY the table data, no explanation""",
    "equation": """Formula Recognition:

Extract any mathematical formulas from the image and output them in LaTeX format (no explanation). Use $...$ for inline and $$...$$ for display formulas.""",
    "text": """Text Recognition:

Extract all text from the image in reading order (top to bottom, left to right). Output ONLY the text, preserving line breaks and paragraph structure. No explanation, no markdown.""",
    "default": """Text Recognition:

Extract all text from the image in reading order. Output ONLY the text. No explanation, no markdown.""",
    "image": """Image Analysis:

Describe what is in the image concisely. Output a short caption describing the image content.""",
    "chart": """Image Analysis:

Describe what is in the chart/image concisely. Output a short caption describing the chart content.""",
}


def detect_task(prompt_text: str) -> str:
    """根据 MinerU 发的 prompt 判断任务类型"""
    if not prompt_text:
        return "default"
    p = prompt_text.lower()
    if "layout detection" in p or "box_start" in p:
        return "layout"
    if "table recognition" in p or "<fcel>" in p:
        return "table"
    if "formula recognition" in p or "equation" in p:
        return "equation"
    if "image analysis" in p:
        return "image"  # chart 也用 image analysis
    if "text recognition" in p or "ocr" in p:
        return "text"
    return "default"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        out = json.dumps({"object": "list",
                          "data": [{"id": MODEL, "object": "model"}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")

        # 从 MinerU 请求提取原始 prompt，判断任务类型
        raw_prompt = ""
        glm_messages = []
        for msg in body.get("messages", []):
            content = msg.get("content")
            if isinstance(content, list):
                parts = []
                for item in content:
                    if item.get("type") == "text":
                        raw_prompt += item["text"] + "\n"
                        parts.append({"type": "text", "text": item["text"]})
                    elif item.get("type") == "image_url":
                        url = item["image_url"]["url"]
                        if url.startswith("data:image"):
                            mime, b64 = url.split(",", 1)
                            parts.append({"type": "image_url",
                                          "image_url": {"url": f"data:image/png;base64,{b64}"}})
                        else:
                            parts.append({"type": "image_url", "image_url": {"url": url}})
                glm_messages.append({"role": msg["role"], "content": parts})
            else:
                raw_prompt += str(content) + "\n"
                glm_messages.append({"role": msg["role"], "content": content})

        task = detect_task(raw_prompt)
        instruction = TASK_INSTRUCTIONS.get(task, TASK_INSTRUCTIONS["default"])

        # 把格式指令注入到包含任务关键词的 user 消息文本（覆盖 MinerU 原始 prompt）
        # 只替换含任务关键词（Layout Detection/Table Recognition等）的文本项
        task_keywords = {
            "layout": "layout detection",
            "table": "table recognition",
            "equation": "formula recognition",
            "image": "image analysis",
            "text": "text recognition",
        }
        kw = task_keywords.get(task, "")
        for msg in glm_messages:
            content = msg.get("content")
            if isinstance(content, list):
                for item in content:
                    if item.get("type") == "text":
                        t = item["text"].lower()
                        if (kw and kw in t) or (not kw and "recognition" in t):
                            item["text"] = instruction
                            break
                break

        # 调试日志
        try:
            with open(LOG_PATH, "a", encoding="utf-8") as fl:
                fl.write(f"[{__import__('datetime').datetime.now()}] task={task} "
                         f"prompt={raw_prompt.strip()[:80]!r}\n")
        except OSError:
            pass

        key = os.environ.get("GLM_API_KEY", "")
        payload = {
            "model": MODEL,
            "messages": glm_messages,
            "temperature": body.get("temperature", 0.0),
            "max_tokens": body.get("max_tokens", 8192),
        }

        req = urllib.request.Request(GLM_URL, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json",
                                              "Authorization": "Bearer " + key})
        # 强制直连 GLM，绕过系统代理（Clash 对 GLM 的 SSL 抖动）
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        # 限流：全局信号量 + 最小间隔，避免 GLM 429
        global _last_request_time
        with _glm_semaphore:
            with _rate_lock:
                now = time.time()
                wait = MIN_REQUEST_INTERVAL - (now - _last_request_time)
                if wait > 0:
                    time.sleep(wait)
                _last_request_time = time.time()
            try:
                resp = opener.open(req, timeout=300)
                data = json.loads(resp.read().decode())
                out = json.dumps(data).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)
            except Exception as e:
                err = json.dumps({"error": str(e)}).encode()
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(err)))
                self.end_headers()
                self.wfile.write(err)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print(f"[GLM代理v2] 监听 127.0.0.1:{PORT}/v1/chat/completions → {MODEL}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
