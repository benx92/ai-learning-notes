"""用独立函数观察重试与调用限额，不实现Agent循环。"""


def with_retry(handler, max_attempts=3):
    if max_attempts < 1:
        raise ValueError("max_attempts至少为1")

    def wrapped(request):
        for attempt in range(1, max_attempts + 1):
            try:
                return handler(request)
            except TimeoutError:
                print(f"重试层：第{attempt}次尝试超时")
                if attempt == max_attempts:
                    raise
    return wrapped


def with_call_limit(handler, limit):
    if limit < 0:
        raise ValueError("limit不能为负数")
    calls = 0

    def wrapped(request):
        nonlocal calls
        if calls >= limit:
            return {"ok": False, "error": "call_limit_exceeded"}
        calls += 1
        print(f"限额层：放行第{calls}次调用")
        return handler(request)
    return wrapped


def main():
    attempts = 0

    def query_demo(request):
        nonlocal attempts
        attempts += 1
        print("进入查询函数")
        if attempts == 1:
            raise TimeoutError("模拟只读查询暂时超时")
        return {"ok": True, "status": "审核中"}

    print("重试实验：一次外部调用，内部查询尝试两次")
    query = with_retry(query_demo, max_attempts=3)
    print(query({"order_id": "A1001"}))

    def model_demo(request):
        print("进入模型替代函数")
        return {"ok": True, "content": "固定响应"}

    print("限额实验：外部发起三次请求，内部只放行两次")
    model_call = with_call_limit(model_demo, limit=2)
    for _ in range(3):
        print(model_call({"question": "查询教学订单"}))


if __name__ == "__main__":
    main()
