from bs4 import BeautifulSoup


if __name__ == "__main__":
    html = """<nav>旧活动：30天退换</nav>
    <article><h1>会员订单退货</h1>
    <p>会员订单签收后15日内可以申请退货。</p></article>"""
    soup = BeautifulSoup(html, "html.parser")
    body = soup.select_one("article")
    if body is None:
        raise ValueError("没有找到正文，请检查页面结构")
    for tag in body.select("script, style, noscript"):
        tag.decompose()
    print(body.get_text(separator="\n", strip=True))
