"""test_block_clean.py — 块级清洗单测（合成数据版，不依赖真实文档，可独立运行）。

覆盖：水印清除、幂等、边界（无 content_list/无 full.md/损坏 json/空 md/无噪音）、
位置感知（text 型页眉/越界/底部正文不误删）、短 key 过滤、代码块内水印、
两入口终点一致性。
"""
import json
import os

from dtmd.clean.block_clean import (
    clean_out_dir, clean_full_md, find_content_list,
    _collect_noise_keys, _load_page_heights,
)


def _synthetic_cl(noise=True, watermark="欢迎加入QQ群123456，免费领500本书"):
    """合成 content_list：10 页，每页含页眉水印 + 页码 + 正文。noise=False 无噪音块。"""
    blocks = []
    for p in range(10):
        if noise:
            blocks.append({"type": "header", "text": watermark,
                           "bbox": [0, 0, 0, 0], "page_idx": p})
            blocks.append({"type": "page_number", "text": str(p + 1),
                           "bbox": [0, 0, 0, 0], "page_idx": p})
        blocks.append({"type": "text", "text": f"这是第{p+1}页的正文内容，需要保留。",
                       "bbox": [0, 0, 0, 0], "page_idx": p})
    return blocks


def _write_case(tmp_path, md_text, cl_blocks, cl_name="abc_content_list.json"):
    """构造一个转写目录：full.md + content_list.json。返回目录路径。"""
    d = tmp_path / "out"
    d.mkdir(parents=True, exist_ok=True)
    (d / "full.md").write_text(md_text, encoding="utf-8")
    (d / cl_name).write_text(json.dumps(cl_blocks, ensure_ascii=False), encoding="utf-8")
    return str(d)


class Test清洗:
    def test_合成水印清除_正文保留(self, tmp_path):
        md = "\n".join("欢迎加入QQ群123456，免费领500本书" for _ in range(5)) + "\n这是第1页的正文内容，需要保留。\n"
        d = _write_case(tmp_path, md, _synthetic_cl())
        r = clean_out_dir(d)
        assert r["ok"] and r["removed"] > 0
        cleaned = open(os.path.join(d, "full.md"), encoding="utf-8").read()
        assert "QQ群" not in cleaned
        assert "正文内容" in cleaned

    def test_幂等_二次清洗零删除(self, tmp_path):
        md = "\n".join("欢迎加入QQ群123456，免费领500本书" for _ in range(5)) + "\n正文\n"
        d = _write_case(tmp_path, md, _synthetic_cl())
        r1 = clean_out_dir(d)
        r2 = clean_out_dir(d)
        assert r1["removed"] > 0
        assert r2["removed"] == 0

    def test_dry_run不写回(self, tmp_path):
        md = "\n".join("欢迎加入QQ群123456，免费领500本书" for _ in range(5)) + "\n正文\n"
        d = _write_case(tmp_path, md, _synthetic_cl())
        r = clean_out_dir(d, dry_run=True)
        assert r["ok"] and r["removed"] > 0
        after = open(os.path.join(d, "full.md"), encoding="utf-8").read()
        assert after == md  # dry_run 不写回


class Test边界:
    def test_无content_list跳过(self, tmp_path):
        d = tmp_path / "out"
        d.mkdir()
        (d / "full.md").write_text("正文", encoding="utf-8")
        r = clean_out_dir(str(d))
        assert r.get("skipped") and "无 content_list" in r["reason"]

    def test_无fullmd跳过(self, tmp_path):
        d = tmp_path / "out"
        d.mkdir()
        (d / "abc_content_list.json").write_text("[]", encoding="utf-8")
        r = clean_out_dir(str(d))
        assert r.get("skipped") and "无 full.md" in r["reason"]

    def test_损坏json不抛异常(self, tmp_path):
        d = tmp_path / "out"
        d.mkdir()
        (d / "abc_content_list.json").write_text("not json{{", encoding="utf-8")
        (d / "full.md").write_text("正文", encoding="utf-8")
        r = clean_out_dir(str(d))
        assert not r.get("ok") and not r.get("skipped") and "error" in r

    def test_空md(self, tmp_path):
        d = _write_case(tmp_path, "", _synthetic_cl())
        r = clean_out_dir(d)
        assert r["ok"] and r["removed"] == 0

    def test_无噪音文档零删除(self, tmp_path):
        md = "第一行正文\n第二行正文\n"
        d = _write_case(tmp_path, md, _synthetic_cl(noise=False))
        r = clean_out_dir(d)
        assert r["ok"] and r["removed"] == 0

    def test_代码块内水印_空代码块清理(self, tmp_path):
        md = "```\n欢迎加入QQ群123456\n```\n正文内容\n"
        cl = [{"type": "header", "text": "欢迎加入QQ群123456",
               "bbox": [0, 0, 0, 0], "page_idx": i} for i in range(5)]
        d = _write_case(tmp_path, md, cl)
        r = clean_out_dir(d)
        cleaned = open(os.path.join(d, "full.md"), encoding="utf-8").read()
        assert "QQ群" not in cleaned
        assert "正文内容" in cleaned
        assert cleaned.count("```") == 0

    def test_find_content_list跳过v2(self, tmp_path):
        d = tmp_path / "out"
        d.mkdir()
        (d / "abc_content_list.json").write_text("[]", encoding="utf-8")
        (d / "abc_content_list_v2.json").write_text("[]", encoding="utf-8")
        found = find_content_list(str(d))
        assert found == os.path.join(str(d), "abc_content_list.json")


class Test位置感知:
    """兜底：MinerU 未标 header 的页眉水印（type=text 但在页面顶部）。"""

    def test_text页眉水印被识别(self):
        blocks = [{"type": "text", "text": "页眉广告水印", "bbox": [0, 20, 0, 40],
                   "page_idx": i} for i in range(5)]
        page_h = {i: 1000 for i in range(5)}  # y0=2% 贴顶
        keys = _collect_noise_keys(blocks, min_pages=3, page_h=page_h)
        assert any("页眉广告水印" in k for k in keys)

    def test_正文中间不误删(self):
        blocks = [{"type": "text", "text": "常见章节词", "bbox": [0, 500, 0, 520],
                   "page_idx": i} for i in range(5)]
        page_h = {i: 1000 for i in range(5)}  # y0=50% 中部
        keys = _collect_noise_keys(blocks, min_pages=3, page_h=page_h)
        assert not any("常见章节词" in k for k in keys)

    def test_底部text不再识别(self):
        blocks = [{"type": "text", "text": "会员账号版权水印", "bbox": [0, 940, 0, 960],
                   "page_idx": i} for i in range(5)]
        page_h = {i: 1000 for i in range(5)}
        keys = _collect_noise_keys(blocks, min_pages=3, page_h=page_h)
        assert not any("会员账号版权水印" in k for k in keys)

    def test_footer类型水印直接收集(self):
        blocks = [{"type": "footer", "text": "异步社区会员woshigedushuren专享尊重版权",
                   "bbox": [0, 0, 0, 0], "page_idx": i} for i in range(5)]
        keys = _collect_noise_keys(blocks, min_pages=3)
        assert any("异步社区会员" in k for k in keys)

    def test_短key过滤(self):
        blocks = [{"type": "footer", "text": "对", "bbox": [0, 0, 0, 0], "page_idx": i}
                  for i in range(5)]
        keys = _collect_noise_keys(blocks, min_pages=3)
        assert keys == set()

    def test_长key保留(self):
        blocks = [{"type": "header", "text": "欢迎加入QQ群123456免费领500本书",
                   "bbox": [0, 0, 0, 0], "page_idx": i} for i in range(5)]
        keys = _collect_noise_keys(blocks, min_pages=3)
        assert any("欢迎加入qq群" in k for k in keys)

    def test_越界bbox不参与位置判定(self):
        blocks = [{"type": "text", "text": "越界块", "bbox": [0, 1390, 0, 1420],
                   "page_idx": i} for i in range(5)]
        page_h = {i: 1000 for i in range(5)}
        keys = _collect_noise_keys(blocks, min_pages=3, page_h=page_h)
        assert not any("越界块" in k for k in keys)

    def test_底部教学正文不误删(self):
        blocks = [
            {"type": "text", "text": "我们先安装它：", "bbox": [0, 500, 0, 520], "page_idx": 0},
            {"type": "text", "text": "我们先安装它：", "bbox": [0, 966, 0, 999], "page_idx": 1},
            {"type": "text", "text": "我们先安装它：", "bbox": [0, 317, 0, 348], "page_idx": 2},
            {"type": "text", "text": "我们先安装它：", "bbox": [0, 322, 0, 356], "page_idx": 3},
        ]
        page_h = {i: 1000 for i in range(4)}
        keys = _collect_noise_keys(blocks, min_pages=3, page_h=page_h)
        assert not any("我们先安装它" in k for k in keys)

    def test_无origin_pdf_降级纯type(self):
        assert _load_page_heights(None) is None


class Test终点一致性:
    def test_两入口结果一致(self, tmp_path):
        """同一合成文档走 clean_out_dir 与 clean_full_md 两条路 → 终点逐项一致。"""
        md = "\n".join("欢迎加入QQ群123456，免费领500本书" for _ in range(5)) + "\n正文内容\n"
        cl = _synthetic_cl()
        # 入口 1：clean_out_dir（自动定位）
        d1 = _write_case(tmp_path / "a", md, cl)
        r1 = clean_out_dir(d1)
        c1 = open(os.path.join(d1, "full.md"), encoding="utf-8").read()
        # 入口 2：clean_full_md（显式指定）
        d2 = tmp_path / "b"
        d2.mkdir()
        m2 = d2 / "full.md"
        m2.write_text(md, encoding="utf-8")
        cl_path = os.path.join(str(d2), "abc_content_list.json")
        with open(cl_path, "w", encoding="utf-8") as f:
            json.dump(cl, f, ensure_ascii=False)
        r2 = clean_full_md(cl_path, str(m2))
        c2 = m2.read_text(encoding="utf-8")
        assert r1["removed"] == r2["removed"]
        assert r1["original_lines"] == r2["original_lines"]
        assert c1 == c2
