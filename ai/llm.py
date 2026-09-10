import os

from langchain_openai import ChatOpenAI

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"


def get_llm() -> ChatOpenAI:
    """构造 DeepSeek 的对话模型实例。

    使用 deepseek-chat 而非 deepseek-reasoner，因为只有前者支持 function calling。
    """
    return ChatOpenAI(
        model=os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL),
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL),
        temperature=0.3,
        max_retries=2,
    )
