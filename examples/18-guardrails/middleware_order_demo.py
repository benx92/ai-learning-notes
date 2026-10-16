def tool_body(request):
    print("工具：执行教学查询")
    return {"ok": True, "status": "审核中"}



def allow_query_only(handler):
    def call(request):
        if request.get("name") != "get_refund_status":
            print("检查：拒绝未知工具")
            return {"ok": False, "error": "tool_not_allowed"}
        print("检查：允许查询工具")
        return handler(request)
    return call



def with_trace(handler):
    def call(request):
        print("记录：调用开始")
        try:
            return handler(request)
        finally:
            print("记录：调用结束")
    return call


if __name__ == "__main__":
    execute = with_trace(allow_query_only(tool_body))

    print("--- 允许的请求 ---")
    print(execute({"name": "get_refund_status"}))

    print("--- 不允许的请求 ---")
    print(execute({"name": "submit_anything"}))
