import streamlit as st
import pandas as pd
import requests
import io
import re
import urllib.parse

# --- 1. 基礎工具函數 ---
def clean_for_match(text):
    if not isinstance(text, str): return ""
    text = text.translate(str.maketrans(
        '０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ（）',
        '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ()'
    ))
    text = re.sub(r'\(JP\d+.*?\)', '', text)
    text = re.sub(r'\(USP.*?\)', '', text)
    text = re.sub(r'\(NF.*?\)', '', text)
    text = re.sub(r'[※\*]\d+', '', text)
    text = text.replace('－', '-').replace(' ', '').replace('　', '')
    return text.strip()

# --- 2. 外部翻譯資源函數 ---

# A. Wikipedia 翻譯 (利用 Wiki 的語言鏈接)
def translate_via_wiki(jap_name):
    try:
        # 先找日文 Wiki 頁面
        search_url = f"https://ja.wikipedia.org/w/api.php?action=query&prop=langlinks&lllang=en&titles={urllib.parse.quote(jap_name)}&format=json"
        res = requests.get(search_url, timeout=5).json()
        pages = res.get('query', {}).get('pages', {})
        for k, v in pages.items():
            if 'langlinks' in v:
                return v['langlinks'][0]['*'] # 返回英文頁面標題
    except:
        pass
    return None

# B. Azure Translator 翻譯
def translate_via_azure(text, api_key, region):
    if not api_key or not region: return None
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
def fetch_and_fill_all_sources(input_df, azure_key, azure_region):
    target_col = '成分名 (日)'
    eng_col = '成分名 (英)'
    id_col = 'KEGG_ID'

    # 取得 KEGG 對照表
    url = "https://rest.kegg.jp/list/dr_ja"
    kegg_res = requests.get(url, timeout=20)
    kegg_ref = []
    for line in kegg_res.text.strip().split('\n'):
        parts = line.split('\t')
        if len(parts) < 2: continue
        d_id = "dr_ja:" + parts[0].replace("dr:", "")
        full_info = parts[1]
        eng_match = re.search(r'\(([^)]+)\)$', full_info)
        kegg_ref.append({
            'id': d_id,
            'cleaned_name': clean_for_match(full_info),
            'eng': eng_match.group(1) if eng_match else ""
        })

    # 執行逐行補齊
    progress_bar = st.progress(0)
    total = len(input_df)

    for i, row in input_df.iterrows():
        jap_name = str(row[target_col])
        clean_name = clean_for_match(jap_name)
        
        # 第一步：嘗試 KEGG (ID + 英文名)
        if pd.isna(row.get(id_col)) or str(row.get(id_col)).strip() in ["", "nan"]:
            found_id, found_eng = None, None
            # 模糊比對邏輯... (簡化版)
            for ref in kegg_ref:
                if clean_name in ref['cleaned_name']:
                    found_id, found_eng = ref['id'], ref['eng']
                    break
            
            if found_id:
                input_df.at[i, id_col] = found_id
                if pd.isna(row.get(eng_col)) or str(row.get(eng_col)).strip() == "":
                    input_df.at[i, eng_col] = found_eng

        # 第二步：如果英文名仍為空，嘗試 Wikipedia
        if pd.isna(input_df.at[i, eng_col]) or str(input_df.at[i, eng_col]).strip() == "":
            wiki_eng = translate_via_wiki(clean_name)
            if wiki_eng:
                input_df.at[i, eng_col] = f"{wiki_eng} (Wiki)"

        # 第三步：如果英文名仍為空，嘗試 Azure Translator
        if pd.isna(input_df.at[i, eng_col]) or str(input_df.at[i, eng_col]).strip() == "":
            azure_eng = translate_via_azure(jap_name, azure_key, azure_region)
            if azure_eng:
                input_df.at[i, eng_col] = f"{azure_eng} (Azure)"

        progress_bar.progress((i + 1) / total)
    
    return input_df

# --- 4. Streamlit UI ---
st.title("💊 藥品全方位翻譯與補齊系統")

with st.sidebar:
    st.header("API 設定")
    azure_key = st.text_input("Azure API Key", type="password")
    azure_region = st.text_input("Azure Region (如 eastasia)")

uploaded_file = st.file_uploader("上傳 CSV 檔案", type=['csv'])

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    if st.button("執行多層級補齊"):
        result_df = fetch_and_fill_all_sources(df.copy(), azure_key, azure_region)
        st.success("補齊完成！")
        
        # 統計來源
        azure_count = result_df[eng_col].str.contains("(Azure)", na=False).sum()
        wiki_count = result_df[eng_col].str.contains("(Wiki)", na=False).sum()
        kegg_count = result_df[id_col].notna().sum()
        
        st.write(f"📊 統計：KEGG 補齊 {kegg_count} 項 | Wiki 翻譯 {wiki_count} 項 | Azure 翻譯 {azure_count} 項")
        st.dataframe(result_df)
        
        csv = result_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下載結果", data=csv, file_name="MultiSource_Drug_List.csv")
