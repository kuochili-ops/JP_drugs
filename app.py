import pandas as pd
import requests

def fetch_and_fill_kegg_data(input_df):
    # 1. 確保原始資料欄位名稱一致
    # 這裡假設你的原始欄位是 'KEGG_ID' 和 '成分名 (英)'
    
    print("正在從 KEGG 下載最新對照數據...")
    url = "https://rest.kegg.jp/list/dr_ja"
    try:
        response = requests.get(url)
        response.raise_for_status()
    except Exception as e:
        print(f"無法連接至 KEGG API: {e}")
        return input_df

    # 2. 解析 KEGG 原始數據
    kegg_data = []
    for line in response.text.strip().split('\n'):
        parts = line.split('\t')
        if len(parts) < 2: continue
        
        k_id = parts[0].replace("dr:", "")
        full_info = parts[1]
        
        # 提取日文名
        jap_name = full_info.split(';')[0].split(' (')[0].strip()
        
        # 提取英文成分名
        eng_name = ""
        if "(" in full_info and ")" in full_info:
            eng_name = full_info[full_info.rfind("(")+1 : full_info.rfind(")")]
        
        kegg_data.append({'品項名稱': jap_name, 'KEGG_ID_REF': k_id, 'ENG_REF': eng_name})

    # 轉成 DataFrame 並移除重複的日文名，確保對應唯一
    ref_df = pd.DataFrame(kegg_data).drop_duplicates('品項名稱')

    # 3. 合併資料
    # 使用 left join 將參考資料拉進來
    merged = pd.merge(input_df, ref_df, on='品項名稱', how='left')

    # 4. 補齊空缺 (如果原本是 NaN，就填入查到的值)
    # 我們這裡直接使用引用的欄位名稱確保不會 Key Error
    if 'KEGG_ID' in merged.columns:
        merged['KEGG_ID'] = merged['KEGG_ID'].fillna(merged['KEGG_ID_REF'])
    else:
        merged['KEGG_ID'] = merged['KEGG_ID_REF']

    if '成分名 (英)' in merged.columns:
        merged['成分名 (英)'] = merged['成分名 (英)'].fillna(merged['ENG_REF'])
    else:
        merged['成分名 (英)'] = merged['ENG_REF']

    # 5. 移除暫存參考欄位並返回
    return merged.drop(columns=['KEGG_ID_REF', 'ENG_REF'])
