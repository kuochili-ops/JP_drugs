import pandas as pd
import requests
import io
import re

# 1. 取得 KEGG 本地字典 (從您提供的 URL)
@st.cache_data # 如果在 Streamlit 環境
def get_kegg_dict():
    url = "https://rest.kegg.jp/list/drug_ja/"
    response = requests.get(url)
    kegg_map = {}
    if response.status_code == 200:
        for line in response.text.strip().split('\n'):
            parts = line.split('\t')
            if len(parts) >= 2:
                kegg_id = parts[0].replace('dr:', '')
                # 名稱通常格式為: 日文名 (英文名); 其他名
                names = parts[1]
                jp_match = re.search(r'^(.+?)\s*\((.+?)\)', names)
                if jp_match:
                    jp_name = jp_match.group(1).strip()
                    en_name = jp_match.group(2).strip()
                    kegg_map[jp_name] = {"id": kegg_id, "en": en_name}
    return kegg_map

# 2. 核心翻譯與比對函數
def process_data(input_csv_path, kegg_dict):
    df = pd.read_csv(input_csv_path)
    
    # 建立一個術語翻譯字典 (補足 Azure 沒翻到的部分)
    term_map = {
        "薬効分類": "藥效分類",
        "選定理由概要": "選定理由摘要",
        "血液凝固阻止剤": "抗凝血劑",
        "他に分類されない代謝性医薬品": "其他類別代謝藥物",
        "継続成分": "持續成分",
        "新規成分": "新成分"
    }

    for idx, row in df.iterrows():
        original_jp = str(row['成分名 (日)']).replace('\n', '').strip()
        # 清理名稱（去除如 "水和物" 等括號）
        clean_jp = re.sub(r'[（\(].*?[）\)]', '', original_jp)
        
        # --- KEGG 比對 ---
        if clean_jp in kegg_dict:
            df.at[idx, 'KEGG_ID'] = kegg_dict[clean_jp]['id']
            df.at[idx, '成分名 (英)'] = kegg_dict[clean_jp]['en']
        
        # --- 翻譯處理 (模擬 Azure 邏輯) ---
        # 這裡針對整列的日文欄位進行替換
        for col in df.columns:
            if df.dtypes[col] == object:
                val = str(df.at[idx, col])
                for jp_term, tw_term in term_map.items():
                    val = val.replace(jp_term, tw_term)
                df.at[idx, col] = val

    return df

# 使用範例
# kegg_lookup = get_kegg_dict()
# final_df = process_data("2026-01-09T06-10_export.csv", kegg_lookup)
# final_df.to_csv("fixed_data.csv", index=False, encoding="utf-8-sig")
