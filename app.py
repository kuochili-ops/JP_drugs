import streamlit as st
import pandas as pd
import requests
import io
import re
import urllib.parse

# --- 1. 工具函數：比對用清洗 (不影響原始顯示) ---
def normalize_for_match(text):
    if not isinstance(text, str): return ""
    text = text.translate(str.maketrans(
        '０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ（）',
        '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ()'
    ))
    text = re.sub(r'\(JP\d+.*?\)', '', text)
    text = re.sub(r'\(USP.*?\)', '', text)
    text = re.sub(r'\(NF.*?\)', '', text)
    text = re.sub(r'[※\*]\d+', '', text)
    text = text.replace('－', '-').replace(' ', '').replace('　', '').replace('\n', '')
    return text.strip()

# --- 2. 外部翻譯資源 ---
def translate_via_wiki(jap_text):
    try:
        url = f"https://ja.wikipedia.org/w/api.php?action=query&prop=langlinks&lllang=en&titles={urllib.parse.quote(jap_text)}&format=json"
        res = requests.get(url, timeout=5).json()
        pages = res.get('query', {}).get('pages', {})
        for k, v in pages.items():
            if 'langlinks' in v:
                return v['langlinks'][0]['*']
    except:
        pass
    return None

def translate_via_azure(text, api_key, region):
    if not api_key or not region or not text: return None
    endpoint = "https://api.cognitive.microsofttranslator.com/translate"
    params = {'api-version': '3.0', 'from': 'ja', 'to': 'en'}
    headers = {
        'Ocp-Apim-Subscription-Key': api_key,
        'Ocp-Apim-Subscription-Region': region,
        'Content-type': 'application/json'
    }
    body = [{'text': text}]
    try:
        res = requests.post(endpoint, params=params, headers=headers, json=body, timeout=5)
        return res.json()[0]['translations'][0]['text']
    except:
        return None

# --- 3. 核心處理邏輯 ---
def process_drug_data(df, azure_key, azure_region):
    COL_JAP = '成分名 (日)'
    COL_ENG = '成分名 (英)'
    COL_ID = 'KEGG_ID'
    COL_CAT_JAP = '藥效分類'
    COL_CAT_ENG = '藥效分類 (英)'

    if COL_CAT_ENG not in df.columns:
        df[COL_CAT_ENG] = ""

    try:
        kegg_res = requests.get("https://rest.kegg.jp/list/dr_ja", timeout=20)
        kegg_ref = []
        for line in kegg_res.text.strip().split('\n'):
            parts = line.split('\t')
            if len(parts) < 2: continue
            d_id = "dr_ja:" + parts[0].replace("dr:", "")
            full_info = parts[1]
            eng_match = re.search(r'\(([^)]+)\)$', full_info)
            kegg_ref.append({
                'id': d_id,
                'match_name': normalize_for_match(full_info),
                'eng': eng_match.group(1) if eng_match else ""
            })
    except:
        st.error("KEGG 資料庫連線失敗")
        return None

    progress_bar = st.progress(0)
    total = len(df)

    for i, row in df.iterrows():
        jap_raw = str(row[COL_JAP])
        jap_clean = normalize_for_match(jap_raw)
        
        # 補齊 KEGG_ID 與成分英文
        if pd.isna(row.get(COL_ID)) or str(row.get(COL_ID)).strip() in ["", "nan"]:
            for ref in kegg_ref:
                if jap_clean in ref['match_name'] or \
                   ('・' in jap_clean and all(p in ref['match_name'] for p in jap_clean.split('・'))):
                    df.at[i, COL_ID] = ref['id']
                    if pd.isna(row.get(COL_ENG)) or str(row.get(COL_ENG)).strip() == "":
                        df.at[i, COL_ENG] = ref['eng']
                    break

        # 補齊成分英文 (Wiki/Azure)
        if pd.isna(df.at[i, COL_ENG]) or str(df.at[i, COL_ENG]).strip() in ["", "nan"]:
            wiki_res = translate_via_wiki(jap_clean)
            if wiki_res:
                df.at[i, COL_ENG] = f"{wiki_res} (Wiki)"
            else:
                azure_res = translate_via_azure(jap_raw, azure_key, azure_region)
                if azure_res:
                    df.at[i, COL_ENG] = f"{azure_res} (Azure)"

        # 藥效分類翻譯
        cat_jap = str(row.get(COL_CAT_JAP, ""))
        if cat_jap and cat_jap != "nan" and (pd.isna(df.at[i, COL_CAT_ENG]) or str(df.at[i, COL_CAT_ENG]).strip() == ""):
            cat_wiki = translate_via_wiki(cat_jap)
            if cat_wiki:
                df.at[i, COL_CAT_ENG] = cat_wiki
            else:
                cat_azure = translate_via_azure(cat_jap, azure_key, azure_region)
                if cat_azure:
                    df.at[i, COL_CAT_ENG] = cat_azure

        progress_bar.progress((i + 1) / total)
    return df

# --- 4. UI ---
st.set_page_config(page_title="藥品清單翻譯補齊系統", layout="wide")
st.title("💊 藥品清單全方位補齊系統")

with st.sidebar:
    st.header("🔑 API 設定")
    az_key = st.text_input("Azure API Key", type="password")
    az_region = st.text_input("Azure Region", value="eastasia")

uploaded_file = st.file_uploader("上傳 CSV 檔案", type=['csv'])

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    if st.button("啟動自動補齊與翻譯"):
        with st.spinner("程序執行中..."):
            result_df = process_drug_data(df.copy(), az_key, az_region)
            if result_df is not None:
                st.success("全部完成！")
                st.dataframe(result_df)

                # --- 下載區塊 (解決 .bin 檔問題) ---
                csv_string = result_df.to_csv(index=False, encoding='utf-8-sig') # 轉換為字串並加上 BOM 防止亂碼
                
                st.download_button(
                    label="📥 下載更新後的 CSV 檔案",
                    data=csv_string,
                    file_name="Drug_List_Updated.csv",
                    mime="text/csv" # 明確指定為 CSV
                )
