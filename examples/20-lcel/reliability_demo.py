"""有限重试与失败回退；不请求网络，不执行业务写入。"""

from langchain_core.runnables import RunnableLambda


def run_retry_demo():
    attempts = []

    def temporary_lookup(value):
        attempts.append(value)
        if len(attempts) < 3:
            raise TimeoutError("模拟只读查询暂时超时")
        return "教学查询恢复"

    step = RunnableLambda(temporary_lookup).with_retry(
        retry_if_exception_type=(TimeoutError,),
        stop_after_attempt=3,
        wait_exponential_jitter=False,
    )
    result = step.invoke("policy-demo")
    return {"attempts": len(attempts), "result": result}


def run_fallback_demo():
    def unavailable(value):
        raise TimeoutError("模拟持续不可用")

    primary = RunnableLambda(unavailable)
    fallback = RunnableLambda(lambda value: "暂时无法取得资料，尚未完成政策核对。")
    step = primary.with_fallbacks([fallback], exceptions_to_handle=(TimeoutError,))
    return step.invoke("policy-demo")


if __name__ == "__main__":
    print(run_retry_demo())
    print(run_fallback_demo())
