"""有限重试与失败回退；不请求网络，不执行业务写入。"""

from langchain_core.runnables import RunnableLambda


def run_retry_demo():
    # 一次实验共用这份列表，用于统计实际执行了几次。
    attempts = []

    def temporary_lookup(value):
        # 用列表记录实际执行次数；前两次失败，第三次成功。
        attempts.append(value)
        if len(attempts) < 3:
            raise TimeoutError("模拟只读查询暂时超时")
        return "教学查询恢复"

    # 重试仅包住这一个只读步骤；不把其他已成功步骤一起重跑。
    step = RunnableLambda(temporary_lookup).with_retry(
        retry_if_exception_type=(TimeoutError,),  # 只有超时才重试，其他异常继续抛出。
        stop_after_attempt=3,  # 包含首次，总共最多执行3次。
        wait_exponential_jitter=False,  # 为快速观察次数关闭等待，不作为线上退避配置。
    )
    # invoke才开始执行；成功后同时交回结果与尝试次数。
    result = step.invoke("policy-demo")
    return {"attempts": len(attempts), "result": result}


def run_fallback_demo():
    def unavailable(value):
        # 主处理始终失败，用它触发备用路径。
        raise TimeoutError("模拟持续不可用")

    primary = RunnableLambda(unavailable)
    # 备用处理只说明未完成核对，不生成一个看似成功的政策结论。
    fallback = RunnableLambda(lambda value: "暂时无法取得资料，尚未完成政策核对。")
    # 只接住TimeoutError；这里没有配置重试，主步骤超时后直接进入备用处理。
    step = primary.with_fallbacks([fallback], exceptions_to_handle=(TimeoutError,))
    # 主处理收到policy-demo，超时后备用处理接收同一份原始输入。
    return step.invoke("policy-demo")


if __name__ == "__main__":
    print(run_retry_demo())
    print(run_fallback_demo())
