"""cli 模块测试：命令解析 + 版本标志 + 参数防呆（不触真实数据）"""
import pytest

from dtmd import cli


def test_parser_accepts_all_commands():
    ap = cli.build_parser()
    for cmd in cli.COMMANDS:
        args = ap.parse_args([cmd])
        assert args.cmd == cmd


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as e:
        cli.build_parser().parse_args(["--version"])
    assert e.value.code == 0
    assert "dtmd" in capsys.readouterr().out


def test_main_no_command_returns_1():
    assert cli.main([]) == 1  # 无子命令 → 打帮助并返回 1


def test_main_negative_limit_exits():
    with pytest.raises(SystemExit):
        cli.main(["list", "--limit", "-1"])  # 负数防呆 → ap.error


def test_scope_choices_valid():
    ap = cli.build_parser()
    args = ap.parse_args(["list", "--scope", "complex"])
    assert args.scope == "complex"
