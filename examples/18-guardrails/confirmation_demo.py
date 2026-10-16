def submit_demo(request):
    print("进入业务函数")
    return {"ok": True, "status": "submitted"}


def require_confirmation(handler):
    def wrapped(request):
        # 本实验用布尔值观察拦截；实际状态必须来自受信任的确认记录。
        if request["confirmed"] is not True:
            return {"ok": False, "error": "confirmation_required"}
        return handler(request)
    return wrapped


def with_trace(handler):
    def wrapped(request):
        print("开始尝试")
        try:
            return handler(request)
        finally:
            print("结束尝试")
    return wrapped


if __name__ == "__main__":
    run = with_trace(require_confirmation(submit_demo))
    print(run({"confirmed": False}))
    print(run({"confirmed": True}))
