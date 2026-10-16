import csv
import io
import json
import xml.etree.ElementTree as ET


if __name__ == "__main__":
    csv_text = '客户类型,说明\n会员,"签收后15日内,定制商品除外"\n'
    for record in csv.DictReader(io.StringIO(csv_text, newline="")):
        print("CSV：", record)
    json_text = '{"policies":[{"customer":"会员","return_days":15}]}'
    for record in json.loads(json_text)["policies"]:
        print("JSON：", record)
    jsonl_text = '{"customer":"会员","return_days":15}\n\n{"customer":"普通订单","return_days":7}'
    for line_number, line in enumerate(jsonl_text.splitlines(), 1):
        if line.strip():
            print("JSONL行号：", line_number, json.loads(line))
    xml_text = '<policies><policy customer="会员"><return_days>15</return_days></policy></policies>'
    for element in ET.fromstring(xml_text).findall("policy"):
        print("XML：", {"customer": element.get("customer"),
                       "return_days": element.findtext("return_days")})
