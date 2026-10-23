"""
CI 门禁阈值检查（独立版本）
四维度质量关卡：性能/安全/代码质量/断言
"""
import json
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


@dataclass
class ThresholdRule:
    """阈值规则"""
    name: str
    operator: str  # <=, >=, ==, !=
    threshold: float
    actual: float = 0.0
    passed: bool = False
    message: str = ""


@dataclass
class QualityGateResult:
    """门禁检查结果"""
    gate_name: str
    environment: str
    passed: bool = False
    performance: List[ThresholdRule] = field(default_factory=list)
    security: List[ThresholdRule] = field(default_factory=list)
    quality: List[ThresholdRule] = field(default_factory=list)
    assertion: List[ThresholdRule] = field(default_factory=list)
    rollback: bool = False
    report: str = ""


class EnvironmentConfig:
    """环境配置"""
    
    CONFIGS = {
        "dev": {
            "name": "开发环境",
            "performance": {
                "avg_response_time": {"operator": "<=", "threshold": 500},
                "p95_response_time": {"operator": "<=", "threshold": 1000},
                "p99_response_time": {"operator": "<=", "threshold": 2000},
                "failure_rate": {"operator": "<=", "threshold": 0.05},
                "error_rate": {"operator": "<=", "threshold": 0.03},
                "qps": {"operator": ">=", "threshold": 50},
            },
            "security": {
                "critical_vulnerabilities": {"operator": "<=", "threshold": 2},
                "high_vulnerabilities": {"operator": "<=", "threshold": 5},
                "medium_vulnerabilities": {"operator": "<=", "threshold": 10},
            },
            "quality": {
                "code_coverage": {"operator": ">=", "threshold": 0.60},
                "code_smells": {"operator": "<=", "threshold": 20},
                "test_pass_rate": {"operator": ">=", "threshold": 0.80},
            },
        },
        "staging": {
            "name": "测试环境",
            "performance": {
                "avg_response_time": {"operator": "<=", "threshold": 300},
                "p95_response_time": {"operator": "<=", "threshold": 800},
                "p99_response_time": {"operator": "<=", "threshold": 1500},
                "failure_rate": {"operator": "<=", "threshold": 0.02},
                "error_rate": {"operator": "<=", "threshold": 0.01},
                "qps": {"operator": ">=", "threshold": 100},
            },
            "security": {
                "critical_vulnerabilities": {"operator": "<=", "threshold": 0},
                "high_vulnerabilities": {"operator": "<=", "threshold": 2},
                "medium_vulnerabilities": {"operator": "<=", "threshold": 5},
            },
            "quality": {
                "code_coverage": {"operator": ">=", "threshold": 0.80},
                "code_smells": {"operator": "<=", "threshold": 10},
                "test_pass_rate": {"operator": ">=", "threshold": 0.95},
            },
        },
        "prod": {
            "name": "生产环境",
            "performance": {
                "avg_response_time": {"operator": "<=", "threshold": 200},
                "p95_response_time": {"operator": "<=", "threshold": 500},
                "p99_response_time": {"operator": "<=", "threshold": 1000},
                "failure_rate": {"operator": "<=", "threshold": 0.01},
                "error_rate": {"operator": "<=", "threshold": 0.005},
                "qps": {"operator": ">=", "threshold": 500},
            },
            "security": {
                "critical_vulnerabilities": {"operator": "<=", "threshold": 0},
                "high_vulnerabilities": {"operator": "<=", "threshold": 0},
                "medium_vulnerabilities": {"operator": "<=", "threshold": 5},
            },
            "quality": {
                "code_coverage": {"operator": ">=", "threshold": 0.90},
                "code_smells": {"operator": "<=", "threshold": 5},
                "test_pass_rate": {"operator": ">=", "threshold": 0.98},
            },
        },
    }
    
    @classmethod
    def get_config(cls, environment: str) -> Dict:
        """获取环境配置"""
        env = environment.lower()
        if env not in cls.CONFIGS:
            logger.warning(f"未知环境 '{environment}'，使用默认配置")
            env = "dev"
        return cls.CONFIGS[env]


class QualityGateChecker:
    """质量门禁检查器"""
    
    def __init__(self, environment: str = "dev", auto_rollback: bool = False):
        self.environment = environment
        self.auto_rollback = auto_rollback
        self.config = EnvironmentConfig.get_config(environment)
    
    def check(
        self,
        metrics: Dict[str, Any],
        gate_name: str = "CI 门禁检查",
    ) -> QualityGateResult:
        """执行门禁检查"""
        result = QualityGateResult(
            gate_name=gate_name,
            environment=self.config["name"],
        )
        
        # 1. 性能维度检查
        result.performance = self._check_dimension(
            "performance",
            metrics.get("performance", {}),
        )
        
        # 2. 安全维度检查
        result.security = self._check_dimension(
            "security",
            metrics.get("security", {}),
        )
        
        # 3. 代码质量维度检查
        result.quality = self._check_dimension(
            "quality",
            metrics.get("quality", {}),
        )
        
        # 4. 断言维度检查
        result.assertion = self._check_assertions(
            metrics.get("assertion", {}),
        )
        
        # 5. 综合判定
        all_rules = result.performance + result.security + result.quality + result.assertion
        result.passed = all(r.passed for r in all_rules)
        
        # 6. 自动回滚
        if not result.passed and self.auto_rollback:
            result.rollback = True
            logger.warning(f"门禁检查失败，触发自动回滚")
        
        # 7. 生成报告
        result.report = self._generate_report(result)
        
        return result
    
    def _check_dimension(
        self,
        dimension: str,
        actual_values: Dict[str, float],
    ) -> List[ThresholdRule]:
        """检查单个维度"""
        rules = []
        config = self.config.get(dimension, {})
        
        for rule_name, rule_config in config.items():
            actual = actual_values.get(rule_name, 0.0)
            threshold = rule_config["threshold"]
            operator = rule_config["operator"]
            
            # 执行比较
            passed = self._compare(actual, operator, threshold)
            
            rule = ThresholdRule(
                name=rule_name,
                operator=operator,
                threshold=threshold,
                actual=actual,
                passed=passed,
                message=self._format_message(rule_name, actual, operator, threshold, passed),
            )
            rules.append(rule)
        
        return rules
    
    def _check_assertions(
        self,
        assertion_metrics: Dict[str, Any],
    ) -> List[ThresholdRule]:
        """检查断言维度"""
        rules = []
        
        # 关键断言通过率必须 100%
        critical_pass_rate = assertion_metrics.get("critical_pass_rate", 1.0)
        rule = ThresholdRule(
            name="关键断言通过率",
            operator="==",
            threshold=1.0,
            actual=critical_pass_rate,
            passed=critical_pass_rate == 1.0,
            message=f"关键断言通过率 {critical_pass_rate:.1%} {'[OK]' if critical_pass_rate == 1.0 else '[FAIL]'}",
        )
        rules.append(rule)
        
        # 业务规则断言
        business_pass_rate = assertion_metrics.get("business_pass_rate", 1.0)
        rule = ThresholdRule(
            name="业务规则断言",
            operator="==",
            threshold=1.0,
            actual=business_pass_rate,
            passed=business_pass_rate == 1.0,
            message=f"业务规则断言通过率 {business_pass_rate:.1%} {'[OK]' if business_pass_rate == 1.0 else '[FAIL]'}",
        )
        rules.append(rule)
        
        return rules
    
    def _compare(self, actual: float, operator: str, threshold: float) -> bool:
        """执行比较"""
        if operator == "<=":
            return actual <= threshold
        elif operator == ">=":
            return actual >= threshold
        elif operator == "==":
            return actual == threshold
        elif operator == "!=":
            return actual != threshold
        else:
            logger.warning(f"未知操作符 '{operator}'")
            return False
    
    def _format_message(
        self,
        name: str,
        actual: float,
        operator: str,
        threshold: float,
        passed: bool,
    ) -> str:
        """格式化消息"""
        status = "[OK]" if passed else "[FAIL]"
        return f"{name}: {actual} {operator} {threshold} {status}"
    
    def _generate_report(self, result: QualityGateResult) -> str:
        """生成报告"""
        lines = [
            f"# CI 门禁报告",
            f"",
            f"## 检查结果：{'[OK] 通过' if result.passed else '[FAIL] 不通过'}",
            f"",
            f"| 维度 | 阈值 | 实际值 | 结果 |",
            f"|------|------|--------|------|",
        ]
        
        # 性能维度
        for rule in result.performance:
            status = "[OK]" if rule.passed else "[FAIL]"
            lines.append(f"| {rule.name} | {rule.operator} {rule.threshold} | {rule.actual} | {status} |")
        
        # 安全维度
        for rule in result.security:
            status = "[OK]" if rule.passed else "[FAIL]"
            lines.append(f"| {rule.name} | {rule.operator} {rule.threshold} | {rule.actual} | {status} |")
        
        # 质量维度
        for rule in result.quality:
            status = "[OK]" if rule.passed else "[FAIL]"
            lines.append(f"| {rule.name} | {rule.operator} {rule.threshold} | {rule.actual} | {status} |")
        
        # 断言维度
        for rule in result.assertion:
            status = "[OK]" if rule.passed else "[FAIL]"
            lines.append(f"| {rule.name} | {rule.operator} {rule.threshold} | {rule.actual} | {status} |")
        
        if result.rollback:
            lines.append(f"\n## [WARN] 自动回滚已触发")
        
        return "\n".join(lines)


def create_checker(environment: str = "dev", auto_rollback: bool = False) -> QualityGateChecker:
    """创建门禁检查器"""
    return QualityGateChecker(environment, auto_rollback)


if __name__ == "__main__":
    # 自测
    print("=== CI 门禁检查自测 ===\n")
    
    # 测试数据
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
    
    # 生产环境检查
    checker = create_checker("prod", auto_rollback=True)
    result = checker.check(metrics, "生产环境门禁检查")
    
    print(f"门禁名称：{result.gate_name}")
    print(f"环境：{result.environment}")
    print(f"检查结果：{'[OK] 通过' if result.passed else '[FAIL] 不通过'}")
    print(f"自动回滚：{'是' if result.rollback else '否'}")
    print(f"\n{result.report}")
    
    # 测试失败场景
    print("\n" + "="*60)
    print("测试失败场景")
    print("="*60 + "\n")
    
    fail_metrics = {
        "performance": {
            "avg_response_time": 350,  # 超过 200ms
            "p95_response_time": 620,  # 超过 500ms
            "p99_response_time": 1200, # 超过 1000ms
            "failure_rate": 0.02,      # 超过 1%
            "error_rate": 0.008,       # 超过 0.5%
            "qps": 400,                # 低于 500
        },
        "security": {
            "critical_vulnerabilities": 1,  # 超过 0
            "high_vulnerabilities": 2,      # 超过 0
            "medium_vulnerabilities": 8,    # 超过 5
        },
        "quality": {
            "code_coverage": 0.85,    # 低于 90%
            "code_smells": 8,         # 超过 5
            "test_pass_rate": 0.96,   # 低于 98%
        },
        "assertion": {
            "critical_pass_rate": 0.95,  # 低于 100%
            "business_pass_rate": 1.0,
        },
    }
    
    fail_result = checker.check(fail_metrics, "生产环境门禁检查（失败）")
    print(f"检查结果：{'[OK] 通过' if fail_result.passed else '[FAIL] 不通过'}")
    print(f"自动回滚：{'是' if fail_result.rollback else '否'}")
    print(f"\n{fail_result.report}")
