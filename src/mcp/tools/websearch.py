"""
WebSearch MCP Tool
"""

from fastmcp import FastMCP
from src.config import get_config
import requests

# 创建独立的 MCP 服务器实例
websearch_mcp = FastMCP("websearch")

class WebSearch:
    """
    WebSearch MCP Tool
    """

    def __init__(self, config=None):
        """
        初始化 WebSearch 工具
        
        Args:
            config: 配置对象（可选，如果不提供则使用默认配置）
        """
        if config is None:
            config = get_config()
        self.config = config
        self.enabled = self.config.tool.websearch.enabled
        self.api_url = self.config.tool.websearch.api_url
        self.api_key = self.config.tool.websearch.api_key

    def search(self, query: str, max_results: int = 5) -> str:
        """
        执行网络搜索

        Args:
            query: 搜索查询词
            max_results: 返回结果数量

        Returns:
            搜索结果的文本摘要
        """
        if not self.enabled:
            return "WebSearch 工具未启用"

        if not self.api_url or not self.api_key:
            return "WebSearch API 配置不完整"

        try:
            # 尝试使用 Tavily SDK
            try:
                from tavily import TavilyClient
                
                tavily_client = TavilyClient(api_key=self.api_key)
                response = tavily_client.search(query, max_results=max_results)
                
                if response and "results" in response:
                    results = response["results"]
                    if results:
                        result_text = "搜索结果：\n"
                        for i, result in enumerate(results, 1):
                            result_text += f"{i}. {result.get('title', '无标题')}\n"
                            result_text += f"   链接：{result.get('url', '无链接')}\n"
                            result_text += f"   摘要：{result.get('content', '无摘要')[:150]}...\n\n"
                        return result_text
                    else:
                        return "搜索成功但未返回结果"
                else:
                    return "搜索响应格式错误"
            
            except ImportError:
                # 如果 Tavily SDK 不可用，使用 HTTP 请求
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}"
                }
                data = {
                    "query": query,
                    "max_results": max_results,
                    "search_depth": "basic"
                }

                response = requests.post(
                    f"{self.api_url}/search",
                    headers=headers,
                    json=data,
                    timeout=10
                )

                if response.status_code == 200:
                    results = response.json()
                    if "results" in results:
                        result_text = "搜索结果：\n"
                        for i, result in enumerate(results["results"], 1):
                            result_text += f"{i}. {result.get('title', '无标题')}\n"
                            result_text += f"   链接：{result.get('url', '无链接')}\n"
                            result_text += f"   摘要：{result.get('content', '无摘要')[:150]}...\n\n"
                        return result_text
                    else:
                        return "搜索成功但未返回结果"
                else:
                    return f"搜索失败：{response.status_code} - {response.text}"

        except Exception as e:
            return f"搜索错误：{str(e)}"


@websearch_mcp.tool(
    name="websearch",
    description="这是一个基于 tavily 的 websearch 工具，用于搜索网络获取最新信息，回答需要实时数据或外部知识的问题"
)
def websearch_tool(query: str, max_results: int = 5) -> str:
    """
    WebSearch 工具调用函数

    Args:
        query: 搜索查询词
        max_results: 返回结果数量

    Returns:
        搜索结果的文本摘要
    """
    searcher = WebSearch()
    return searcher.search(query, max_results)


if __name__ == "__main__":
    websearch_mcp.run(transport="sse")
