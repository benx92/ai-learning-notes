import pymupdf


def read_pdf_page(page, use_ocr=False):
    if use_ocr:
        text_page = page.get_textpage_ocr(
            language="chi_sim+eng", dpi=300, full=True
        )
        return page.get_text("text", textpage=text_page, sort=True)
    return page.get_text("text", sort=True)



if __name__ == "__main__":
    with pymupdf.open("refund-policy.pdf") as document:
        for number, page in enumerate(document, 1):
            text = read_pdf_page(page, use_ocr=False)
            print(f"第{number}页：\n{text}")
