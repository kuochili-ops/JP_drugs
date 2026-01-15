import streamlit as st
import pandas as pd
import requests
import io
import re
import urllib.parse

# --- 1. 基礎工具函數 ---
def normalize_for_match(text):
    if not isinstance(text, str): return ""
    # 轉半形
    text = text.translate(str.maketrans(
        '０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ（）',
        '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ()'
    ))
    # 移除藥典與備註符號 (比對用)
    text = re.sub(r'\(JP\d+.*?\)', '', text)
    text = re.sub(r'\(USP.*?\)', '', text)
    text = re.sub(r'\(NF.*?\)', '', text)
    text = re.sub(r'[※\*]\d+', '', text)
    text = text.replace('－', '-').replace(' ', '').replace('　', '').replace('\n', '')
    return text.strip()

# --- 2. 外部翻譯資源 ---
def translate_via_wiki(jap_text):
    """透過 Wiki 獲取對應英文標題"""
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
    """Azure 翻譯"""
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
    # 欄位定義
    COL_JAP = '成分名 (日)'
    COL_ENG = '成分名 (英)'
    COL_ID = 'KEGG_ID'
    COL_CAT_JAP = '藥效分類'
    COL_CAT_ENG = '藥效分類 (英)'

    # 確保英文分類欄位存在
    if COL_CAT_ENG not in df.columns:
        df[COL_CAT_ENG] = ""

    # 下載 KEGG
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
        # --- A. 成分名與 ID 處理 (KEGG) ---
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

        # --- B. 成分名補齊 (Wiki/Azure) ---
        if pd.isna(df.at[i, COL_ENG]) or str(df.at[i, COL_ENG]).strip() in ["", "nan"]:
            wiki_res = translate_via_wiki(jap_clean)
            if wiki_res:
                df.at[i, COL_ENG] = f"{wiki_res} (Wiki)"
            else:
                azure_res = translate_via_azure(jap_raw, azure_key, azure_region)
                if azure_res:
                    df.at[i, COL_ENG] = f"{azure_res} (Azure)"

        # --- C. 藥效分類翻譯 (Wiki/Azure) ---
        cat_jap = str(row.get(COL_CAT_JAP, ""))
        if cat_jap and cat_jap != "nan":
            # 優先嘗試 Wiki
            cat_wiki = translate_via_wiki(cat_jap)
            if cat_wiki:
                df.at[i, COL_CAT_ENG] = cat_wiki
            else:
                # 失敗則用 Azure
                cat_azure = translate_via_azure(cat_jap, azure_key, azure_region)
                if cat_azure:
                    df.at[i, COL_CAT_ENG] = cat_azure

        progress_bar.progress((i + 1) / total)
    
    return df

# --- 4. UI ---
st.set_page_config(page_title="藥品清單翻譯補齊系統", layout="wide")
st.title("💊 藥品清單全方位補齊系統")
st.markdown("補齊 `KEGG_ID`、`成分名 (英)` 並將 `藥效分類` 翻譯為英文。")

with st.sidebar:
    st.header("🔑 API 設定")
    az_key = st.text_input("Azure API Key", type="password")
    az_region = st.text_input("Azure Region", value="eastasia")

uploaded_file = st.file_uploader("上傳 CSV 檔案", type=['csv'])

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    st.write("### 原始資料預覽")
    st.dataframe(df.head(5))

    if st.button("啟動自動補齊與翻譯"):
        with st.spinner("程序執行中，請稍候..."):
            result_df = process_drug_data(df.copy(), az_key, az_region)
            
            if result_df is not None:
                st.success("全部完成！")
                
                # 統計
                k_filled = result_df['KEGG_ID'].notna().sum()
                c_filled = (result_df['藥效分類 (英)'].str.strip() != "").sum()
                
                c1, c2 = st.columns(2)
                c1.metric("KEGG 補齊數", k_filled)
                c2.metric("分類翻譯數", c_filled)

                st.dataframe(result_df)

                # 下載
                output = io.BytesIO()
                result_df.to_csv(output, index=False, encoding='utf-8-sig')
                st.download_button("📥 下載更新後的 CSV", output.getvalue(), "Drug_List_Translated.csv")
