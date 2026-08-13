"""config 模块测试：环境变量读取 + 端口兜底 + 工具路径解析"""
import importlib

import pytest

import dtmd.config as config


def test_proxy_port_default(monkeypatch):
    monkeypatch.delenv("DTM_PROXY_PORT", raising=False)
    mod = importlib.reload(config)
    assert mod.PROXY_PORT == 8031


def test_proxy_port_invalid_falls_back(monkeypatch):
    monkeypatch.setenv("DTM_PROXY_PORT", "not-a-port")
    mod = importlib.reload(config)
    assert mod.PROXY_PORT == 8031  # 非法值兜底，避免 import 崩溃


def test_mineru_cli_default(monkeypatch):
    monkeypatch.delenv("DTM_MINERU_ENV", raising=False)
    mod = importlib.reload(config)
    assert mod.mineru_cli() == "mineru"  # 未配置 → 走 PATH


def test_mineru_cli_with_env(monkeypatch, tmp_path):
    env = tmp_path / "venv"
    env.mkdir()
    monkeypatch.setenv("DTM_MINERU_ENV", str(env))
    mod = importlib.reload(config)
    assert mod.mineru_cli() == str(env / "Scripts" / "mineru.exe")
    assert mod.mineru_python() == str(env / "Scripts" / "python.exe")


def test_proxy_script_empty_without_bridge(monkeypatch):
    monkeypatch.delenv("DTM_BRIDGE_DIR", raising=False)
    mod = importlib.reload(config)
    assert mod.proxy_script() == ""  # 未配置代理 → 返回空（跳过）


def test_proxy_script_with_bridge(monkeypatch, tmp_path):
    bridge = tmp_path / "bridge"
    bridge.mkdir()
    monkeypatch.setenv("DTM_BRIDGE_DIR", str(bridge))
    mod = importlib.reload(config)
    assert mod.proxy_script() == str(bridge / "glm_mineru_proxy.py")


def test_pandoc_env_override(monkeypatch):
    monkeypatch.setenv("DTM_PANDOC", "/custom/pandoc")
    mod = importlib.reload(config)
    assert mod.PANDOC == "/custom/pandoc"
