import pandas as pd
import requests

# 1. 定義 KEGG 查詢函數
def get_kegg_info(drug_name_jp):
    # 透過 KEGG API 搜尋成分名
    url = f"https://rest.kegg.jp/find/drug/{drug_name_jp}"
    response = requests.get(url)
    if response.status_code == 200 and response.text:
        # 取得第一筆匹配結果的 ID 與 英文名
        first_line = response.text.split('\n')[0].split('\t')
        kegg_id = first_line[0].replace('dr:', '')
        # 再透過 ID 取得詳細英文名
        info_url = f"https://rest.kegg.jp/get/{kegg_id}"
        info_res = requests.get(info_url)
        # 簡單解析英文名稱 (此處為示意)
        return kegg_id, "English Name from KEGG"
    return "N/A", "N/A"

# 2. 逐項處理數據 (範例循環)
results = []
for row in raw_data:
    kegg_id, eng_name = get_kegg_info(row['成分名'])
    translated_reason = azure_translate(row['選定理由概要']) # 假設串接翻譯
    results.append({
        "成分名(JP/EN)": f"{row['成分名']} ({eng_name})",
        "KEGG ID": kegg_id,
        "選定理由": translated_reason,
        # ... 其他欄位
    })
