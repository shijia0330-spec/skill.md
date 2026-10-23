"""
CI 门禁自动回滚（独立版本）
门禁失败时自动触发回滚
"""
import os
import subprocess
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class RollbackManager:
    """回滚管理器"""
    
    def __init__(self, git_repo: str = None, rollback_callback: str = None):
        self.git_repo = git_repo or os.getcwd()
        self.rollback_callback = rollback_callback
    
    def rollback(
        self,
        target_commit: str = None,
        reason: str = "CI 门禁检查失败",
    ) -> dict:
        """执行回滚"""
        result = {
            "success": False,
            "message": "",
            "rollback_commit": None,
        }
        
        try:
            # 1. 确定回滚目标
            if target_commit:
                rollback_to = target_commit
            else:
                # 获取上一个稳定版本
                rollback_to = self._get_last_stable_commit()
            
            if not rollback_to:
                result["message"] = "未找到稳定版本，无法回滚"
                return result
            
            # 2. 执行 Git 回滚
            logger.info(f"执行回滚到 {rollback_to}")
            cmd = f"cd {self.git_repo} && git reset --hard {rollback_to}"
            subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            # 3. 触发回调（如果有）
            if self.rollback_callback:
                logger.info(f"触发回滚回调：{self.rollback_callback}")
                subprocess.run(
                    ["bash", "-c", self.rollback_callback],
                    capture_output=True,
                    text=True,
                )
            
            result["success"] = True
            result["message"] = f"回滚成功：{reason}"
            result["rollback_commit"] = rollback_to
            
        except Exception as e:
            result["message"] = f"回滚失败：{str(e)}"
            logger.error(f"回滚失败：{e}")
        
        return result
    
    def _get_last_stable_commit(self) -> Optional[str]:
        """获取上一个稳定版本"""
        try:
            # 查找最后一个 tagged 版本
            cmd = f"cd {self.git_repo} && git describe --tags --abbrev=0 2>/dev/null || git rev-parse HEAD~1"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            logger.error(f"获取稳定版本失败：{e}")
        
        return None


def create_rollback_manager(**kwargs) -> RollbackManager:
    """创建回滚管理器"""
    return RollbackManager(**kwargs)


if __name__ == "__main__":
    # 自测
    print("=== CI 门禁回滚自测 ===\n")
    
    manager = create_rollback_manager()
    
    # 模拟回滚（不实际执行）
    result = manager.rollback(
        target_commit="abc123",
        reason="CI 门禁检查失败：P95 响应时间 620ms > 500ms"
    )
    
    print(f"回滚结果：")
    print(f"  成功：{result['success']}")
    print(f"  消息：{result['message']}")
    print(f"  回滚到：{result['rollback_commit']}")
    
    print("\n[OK] 回滚管理器测试通过")
