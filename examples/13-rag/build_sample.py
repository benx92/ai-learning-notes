"""重建文章中的两页虚构 PDF。仅生成样例时需要 reportlab。"""

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas


def build_pdf(target):
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    output = canvas.Canvas(str(target), pagesize=A4)
    output.setTitle("虚构售后政策 - RAG 教学样例")
    pages = [
        ("订单退货期限", ["会员订单签收后 15 日内可以申请退货。",
                        "普通订单签收后 7 日内可以申请退货。"]),
        ("商品例外与退款到账", ["定制商品不支持无理由退货。",
                            "退款将在审核通过后 3 个工作日内到账。"]),
    ]
    for number, (title, lines) in enumerate(pages, 1):
        output.setFillColorRGB(0.12, 0.20, 0.30)
        output.setFont("STSong-Light", 24)
        output.drawString(52, 770, "虚构售后政策")
        output.setFont("STSong-Light", 17)
        output.drawString(52, 720, title)
        output.setStrokeColorRGB(0.75, 0.81, 0.87)
        output.line(52, 698, 543, 698)
        output.setFont("STSong-Light", 14)
        for index, line in enumerate(lines):
            output.drawString(52, 650 - index * 44, line)
        output.setFont("STSong-Light", 10)
        output.setFillColorRGB(0.35, 0.40, 0.46)
        output.drawString(52, 94, "仅用于文档问答测试，不代表实际公司政策或法律规定。")
        output.drawString(52, 72, f"第 {number} 页 / 共 2 页")
        output.showPage()
    output.save()


if __name__ == "__main__":
    build_pdf(Path(__file__).with_name("refund-policy.pdf"))
