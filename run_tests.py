#!/usr/bin/env python3
"""
测试运行脚本
import os
"""
import os
import subprocess
import sys
import time
from pathlib import Path


def run_command(cmd, description):
    """运行命令并输出结果"""
    print(f"\n{'='*60}")
    print(f"🚀 {description}")
    print(f"{'='*60}")
    print(f"命令: {' '.join(cmd)}")

    # 设置环境变量
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).parent)

    start_time = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    end_time = time.time()

    print(f"\n⏱️  执行时间: {end_time - start_time:.2f}秒")
    print(f"退出码: {result.returncode}")

    if result.stdout:
        print(f"\n📄 标准输出:")
        print(result.stdout)

    if result.stderr:
        print(f"\n❌ 错误输出:")
        print(result.stderr)

    return result.returncode == 0


def main():
    """主函数"""
    print("🧪 XianyuAutoAgent 完整测试套件")
    print("=" * 60)

    # 确保在项目根目录
    project_root = Path(__file__).parent
    os.chdir(project_root)

    test_results = []

    # 1. 代码质量检查
    test_results.append(
        ("代码格式化检查", ["uv", "run", "black", "--check", "--diff", "."])
    )

    test_results.append(
        ("导入排序检查", ["uv", "run", "isort", "--check-only", "--diff", "."])
    )

    test_results.append(("代码风格检查", ["uv", "run", "flake8", "."]))

    test_results.append(("类型检查", ["uv", "run", "mypy", "."]))

    # 2. 单元测试
    test_results.append(
        (
            "单元测试",
            [
                "uv",
                "run",
                "pytest",
                "tests/unit/",
                "-v",
                "--cov=.",
                "--cov-report=term-missing",
                "--cov-report=html",
            ],
        )
    )

    # 3. 集成测试
    test_results.append(
        (
            "集成测试",
            [
                "uv",
                "run",
                "pytest",
                "tests/integration/",
                "-v",
                "-m",
                "not performance",
            ],
        )
    )

    # 4. 性能测试
    test_results.append(
        (
            "性能测试",
            ["uv", "run", "pytest", "tests/performance/", "-v", "-m", "performance"],
        )
    )

    # 5. 端到端测试
    test_results.append(
        (
            "端到端测试",
            [
                "uv",
                "run",
                "pytest",
                "tests/integration/test_end_to_end.py",
                "-v",
                "-m",
                "e2e",
            ],
        )
    )

    # 运行所有测试
    passed = 0
    failed = 0

    for description, cmd in test_results:
        try:
            success = run_command(cmd, description)
            if success:
                passed += 1
                print(f"\n✅ {description} 通过")
            else:
                failed += 1
                print(f"\n❌ {description} 失败")
        except Exception as e:
            failed += 1
            print(f"\n❌ {description} 异常: {e}")

    # 总结
    print(f"\n{'='*60}")
    print(f"📊 测试结果总结")
    print(f"{'='*60}")
    print(f"✅ 通过: {passed}")
    print(f"❌ 失败: {failed}")
    print(f"📈 成功率: {passed/(passed+failed)*100:.1f}%")

    if failed == 0:
        print(f"\n🎉 所有测试通过！代码质量优秀！")
        return 0
    else:
        print(f"\n⚠️  有 {failed} 个测试失败，请检查代码")
        return 1


if __name__ == "__main__":
    sys.exit(main())
