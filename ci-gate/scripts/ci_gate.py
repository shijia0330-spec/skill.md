#!/usr/bin/env python3
"""
CI 门禁检查入口脚本
用法：
    python ci_gate.py --env prod --metrics metrics.json
    python ci_gate.py --env dev --auto-rollback
"""
import sys
import os
import argparse
import json

# 添加脚本目录到路径
sys.path.insert(0, os.path.dirname(__file__))

from quality_gate import create_checker
from rollback import create_rollback_manager


def main():
    parser = argparse.ArgumentParser(description="CI 门禁检查")
    parser.add_argument("--env", type=str, default="dev", choices=["dev", "staging", "prod"],
                       help="环境（dev/staging/prod）")
    parser.add_argument("--metrics", type=str, default=None,
                       help="指标 JSON 文件路径")
    parser.add_argument("--auto-rollback", action="store_true",
                       help="门禁失败时自动回滚")
    parser.add_argument("--rollback-callback", type=str, default=None,
                       help="回滚回调命令")
    parser.add_argument("--output", type=str, default="text", choices=["text", "html", "markdown"],
                       help="输出格式")
    parser.add_argument("--gate-name", type=str, default="CI 门禁检查",
                       help="门禁名称")
    args = parser.parse_args()
    
    # 加载指标
    if args.metrics:
        with open(args.metrics) as f:
            metrics = json.load(f)
    else:
        # 默认测试指标
        metrics = {
            "performance": {
                "avg_response_time": 180,
                "p95_response_time": 450,
                "p99_response_time": 800,
                "failure_rate": 0.008,
                "error_rate": 0.003,
                "qps": 600,
            },
            "security": {
                "critical_vulnerabilities": 0,
                "high_vulnerabilities": 0,
                "medium_vulnerabilities": 3,
            },
            "quality": {
                "code_coverage": 0.92,
                "code_smells": 3,
                "test_pass_rate": 0.99,
            },
            "assertion": {
                "critical_pass_rate": 1.0,
                "business_pass_rate": 1.0,
            },
        }
    
    # 执行门禁检查
    checker = create_checker(args.env, auto_rollback=args.auto_rollback)
    result = checker.check(metrics, args.gate_name)
    
    # 输出报告
    if args.output == "text":
        print(result.report)
    elif args.output == "markdown":
        print(result.report)
    elif args.output == "html":
        # 简单 HTML 转换
        html = result.report.replace("\n", "<br>\n").replace("|", "")
        print(f"<html><body>{html}</body></html>")
    
    # 自动回滚
    if result.rollback:
        print(f"\n[WARN] 门禁检查失败，触发自动回滚")
        
        manager = create_rollback_manager(rollback_callback=args.rollback_callback)
        rollback_result = manager.rollback(reason=result.report)
        
        if rollback_result["success"]:
            print(f"[OK] 回滚成功：{rollback_result['rollback_commit']}")
        else:
            print(f"[FAIL] 回滚失败：{rollback_result['message']}")
    
    # 退出码
    sys.exit(0 if result.passed else 1)


if __name__ == "__main__":
    main()
