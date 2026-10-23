"""
RAG 关键词提取（供检索与重排序共用）
"""
import re
from typing import List

STOP_WORDS = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
    "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
    "自己", "这", "那", "里", "啊", "呢", "吧", "什么", "时候", "没", "吗", "谁",
    "他", "她", "它", "们", "这个", "那个", "可以", "应该", "已经", "然后", "但是",
    "如果", "那么", "因为", "所以", "而且", "或者", "还是",
}

TEST_DOMAIN_KEYWORDS = {
    "登录", "注册", "密码", "权限", "验证", "认证", "安全", "加密", "解密",
    "支付", "订单", "购物车", "商品", "库存", "物流", "退款", "售后",
    "搜索", "筛选", "排序", "分页", "列表", "详情", "表单", "提交",
    "上传", "下载", "导入", "导出", "图片", "视频", "音频", "文件",
    "接口", "API", "测试", "用例", "执行", "结果", "报告",
    "性能", "并发", "压力", "响应", "超时", "异常", "错误", "日志",
    "数据库", "缓存", "Redis", "MySQL", "事务", "索引", "查询",
    "前端", "页面", "按钮", "输入", "输出", "显示", "隐藏", "动画",
    "网络", "请求", "状态码", "Cookie", "Session", "Token",
}


def extract_keywords(text: str, top_n: int = 8) -> List[str]:
    """从文本中提取关键词，测试领域关键词优先。"""
    if not text:
        return []

    short_phrases = re.split(r'[，。、；：！？\s\n\r\(\)\[\]{}《》""\'\\,\\.\/\\]+', text)
    short_phrases = [p.strip() for p in short_phrases if p.strip()]

    all_tokens = []
    for phrase in short_phrases:
        if len(phrase) <= 4:
            all_tokens.append(phrase)
        else:
            for size in [4, 3, 2]:
                for i in range(0, len(phrase) - size + 1, max(1, size // 2)):
                    chunk = phrase[i:i + size]
                    if chunk not in STOP_WORDS:
                        all_tokens.append(chunk)

    seen = set()
    unique_tokens = []
    for token in all_tokens:
        if token not in seen and len(token) >= 2 and token not in STOP_WORDS:
            seen.add(token)
            unique_tokens.append(token)

    scored = [(token, 2 if token in TEST_DOMAIN_KEYWORDS else 1) for token in unique_tokens]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [word for word, _ in scored[:top_n]]


def build_search_query(requirement: str) -> str:
    """从需求文本构建搜索查询字符串。"""
    keywords = extract_keywords(requirement, top_n=8)
    return " ".join(keywords)


if __name__ == "__main__":
    # 自测
    print("=== RAG 关键词提取自测 ===\n")
    
    kws = extract_keywords("登录模块的测试用例", top_n=5)
    print(f"提取关键词: {kws}")
    assert "登录" in kws
    assert "测试" in kws
    
    kws = extract_keywords("", top_n=5)
    assert kws == []
    
    kws = extract_keywords("API接口测试 性能测试 登录验证", top_n=3)
    print(f"领域关键词优先: {kws}")
    
    query = build_search_query("登录模块的测试用例")
    print(f"搜索查询: {query}")
    
    print("\n[OK] 所有测试通过")
