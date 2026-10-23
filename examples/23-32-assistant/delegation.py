"""30：真实Agent委派入口，调用方传入模型；另有固定消息实验供离线检查。"""
from langchain.agents import create_agent
from langchain_core.tools import tool


def build_delegation(model, business, policy, user):
    @tool
    def lookup(order_id: str) -> dict:
        """查询当前用户订单事实。"""
        return business.order(order_id, user)

    @tool
    def search(question: str) -> dict:
        """搜索政策并返回来源。"""
        return policy(question)

    orders = create_agent(model=model, tools=[lookup], system_prompt="只核对订单事实，不编造政策。")
    policies = create_agent(model=model, tools=[search], system_prompt="只解释提供的政策证据，保留来源与例外。")

    @tool
    def order_expert(query: str) -> str:
        """将明确的订单核对问题交给订单助手。"""
        result = orders.invoke({"messages": [{"role": "user", "content": query}]},
                               {"recursion_limit": 12})
        return result["messages"][-1].content

    @tool
    def policy_expert(query: str) -> str:
        """将明确的政策问题交给政策助手。"""
        result = policies.invoke({"messages": [{"role": "user", "content": query}]},
                                 {"recursion_limit": 12})
        return result["messages"][-1].content

    supervisor = create_agent(model=model, tools=[order_expert, policy_expert],
                              system_prompt="按需要委派明确问题；综合证据回答。无权批准申请。")
    baseline = create_agent(model=model, tools=[lookup, search],
                            system_prompt="核对订单与政策后回答；保留来源，无权批准申请。")
    return baseline, supervisor
