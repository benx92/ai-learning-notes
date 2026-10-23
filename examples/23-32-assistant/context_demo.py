"""请求上下文实验：两个并发协程只读取自己的身份。"""
import asyncio
from contextvars import ContextVar

current_user = ContextVar("current_user")


async def handle(user):
    token = current_user.set(user)
    try:
        await asyncio.sleep(0)
        return {"input": user, "observed": current_user.get()}
    finally:
        current_user.reset(token)


async def main():
    return await asyncio.gather(handle("alice"), handle("bob"))


if __name__ == "__main__":
    print(asyncio.run(main()))
