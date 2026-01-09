import pandas as pd
import requests
import pdfplumber # 建議使用 pdfplumber 解析表格
import time

# 1. 設置 KEGG API 查詢函數
def get_kegg_details(drug_name_jp):
    """透過 KEGG API 獲取成分的英文名與 ID"""
    try:
        # 搜尋成分
        search_url = f"https://rest.kegg.jp/find/drug/{drug_name_jp}"
        r = requests.get(search_url, timeout=10)
        if r.status_code == 200 and r.text.strip():
            # 取第一筆結果
            first_entry = r.text.split('\n')[0].split('\t')
            kegg_id = first_entry[0].replace('dr:', '')
            
            # 獲取詳細英文名稱
            info_url = f"https://rest.kegg.jp/get/{kegg_id}"
            info_r = requests.get(info_url, timeout=10)
            eng_name = "Unknown"
            for line in info_r.text.split('\n'):
                if line.startswith('NAME'):
                    # 提取第一個英文名並過濾掉日文
                    eng_name = line.replace('NAME', '').strip().split(';')[0]
                    break
            return kegg_id, eng_name
    except:
        pass
    return "N/A", "N/A"

# 2. 定義 Azure 翻譯模擬 (或實際 API 呼叫)
def translate_text(text):
    # 這裡應換成您的 Azure Translator API 呼叫邏輯
    # 範例僅做簡單術語替換或提示
    mapping = {
        "内": "內服", "注": "注射", "外": "外用",
        "継続成分": "持續成分", "新規成分": "新成分"
    }
    for k, v in mapping.items():
        text = text.replace(k, v)
    return text

# 3. 讀取 PDF 並處理 (核心邏輯)
def process_drug_pdf(file_path):
    all_data = []
    
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if not table:
                continue
            
            # 跳過標頭檔 (假設第一列是標題)
            for row in table[1:]:
                # 確保列數正確 (根據您的 PDF 結構調整索引)
                if len(row) < 7: continue
                
                jp_name = row[4].replace('\n', '') # 成分名
                
                # 執行 KEGG 對照
                k_id, en_name = get_kegg_details(jp_name)
                
                # 執行翻譯 (針對分類名與理由)
                processed_row = {
                    "區分": translate_text(row[0]),
                    "途徑": translate_text(row[1]),
                    "藥效代碼": row[2],
                    "藥效分類": translate_text(row[3]),
                    "成分名(日)": jp_name,
                    "成分名(英)": en_name,
                    "KEGG_ID": k_id,
                    "理由摘要": translate_text(row[6]), # 選定理由
                    "R7分類": row[7].strip() if row[7] else ""
                }
                all_data.append(processed_row)
                time.sleep(0.1) # 避免 API 頻率過高
                
    return pd.DataFrame(all_data)

# 執行處理
# df = process_drug_pdf("001586778.pdf")
# df.to_csv("processed_drugs.csv", index=False, encoding="utf-8-sig")
