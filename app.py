import streamlit as st
import pandas as pd
import requests
import io
import re
import urllib.parse

# --- 1. 基礎工具函數 ---
def normalize_for_match(text):
    """僅供比對使用的清洗邏輯：轉半形、移除備註與藥典標記"""
    if not isinstance(text, str): return ""
    # 轉半形
    text = text.translate(str.maketrans(
        '０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ（）',
        '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ()'
    ))
    # 比對時忽略藥典標記 (JP/USP/NF)
    text = re.sub(r'\(JP\d+.*?\)', '', text)
    text = re.sub(r'\(USP.*?\)', '', text)
    text = re.sub(r'\(NF.*?\)', '', text)
    # 忽略 ※ 或 * 備註符號
    text = re.sub(r'[※\*]\d+', '', text)
    # 處理 L/D 前綴符號與空白
    text = text.replace('－', '-').replace(' ', '').replace('　', '').replace('\n', '')
    return text.strip()

# --- 2. 外部翻譯資源 ---
def translate_via_wiki(jap_name):
    """透過 Wikipedia 語言鏈結獲取學名"""
    try:
        search_url = f"https://ja.wikipedia.org/w/api.php?action=query&prop=langlinks&lllang=en&titles={urllib.parse.quote(jap_name)}&format=json"
        res = requests.get(search_url, timeout=5).json()
        pages = res.get('query', {}).get('pages', {})
        for k, v in pages.items():
            if 'langlinks' in v:
                return v['langlinks'][0]['*']
    except:
        pass
    return None

def translate_via_azure(text, api_key, region):
    """透過 Azure Translator 翻譯"""
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

# --- 3. 核心處理函數 ---
def fetch_and_process_data(input_df, azure_key, azure_region):
    TARGET_COL = '成分名 (日)'
    ENG_COL = '成分名 (英)'
    ID_COL = 'KEGG_ID'

    # 下載 KEGG 資料庫
    try:
        kegg_res = requests.get("https://rest.kegg.jp/list/dr_ja", timeout=20)
        kegg_res.raise_for_status()
    except:
        st.error("無法連線至 KEGG 資料庫")
        return None

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

    # 逐行執行補齊
    progress_bar = st.progress(0)
    total = len(input_df)

    for i, row in input_df.iterrows():
        jap_raw = str(row[TARGET_COL])
        jap_clean = normalize_for_match(jap_raw)
        
        # A. 第一優先：KEGG 補齊
        if pd.isna(row.get(ID_COL)) or str(row.get(ID_COL)).strip() in ["", "nan"]:
            for ref in kegg_ref:
                # 模糊比對：包含或拆解比對
                if jap_clean in ref['match_name'] or \
                   ('・' in jap_clean and all(p in ref['match_name'] for p in jap_clean.split('・'))):
                    input_df.at[i, ID_COL] = ref['id']
                    if pd.isna(row.get(ENG_COL)) or str(row.get(ENG_COL)).strip() == "":
                        input_df.at[i, ENG_COL] = ref['eng']
                    break

        # B. 第二優先：Wikipedia 翻譯 (若英文名仍為空)
        current_eng = str(input_df.at[i, ENG_COL])
        if pd.isna(input_df.at[i, ENG_COL]) or current_eng.strip() in ["", "nan"]:
            wiki_res = translate_via_wiki(jap_clean)
            if wiki_res:
                input_df.at[i, ENG_COL] = f"{wiki_res} (Wiki)"

        # C. 第三優先：Azure 翻譯 (若英文名仍為空)
        current_eng = str(input_df.at[i, ENG_COL])
        if pd.isna(input_df.at[i, ENG_COL]) or current_eng.strip() in ["", "nan"]:
            azure_res = translate_via_azure(jap_raw, azure_key, azure_region)
            if azure_res:
                input_df.at[i, ENG_COL] = f"{azure_res} (Azure)"

        progress_bar.progress((i + 1) / total)
    
    return input_df

# --- 4. Streamlit UI ---
st.set_page_config(page_title="藥品資料自動補齊系統", layout="wide")
st.title("💊 藥品資料智慧補齊系統 (整合版)")

with st.sidebar:
    st.header("🔑 翻譯 API 設定")
    az_key = st.text_input("Azure API Key", type="password")
    az_region = st.text_input("Azure Region (如 eastasia)")
    st.info("如無 Azure 金鑰，系統將僅使用 KEGG 與 Wikipedia 資源。")

uploaded_file = st.file_uploader("上傳 CSV 檔案 (欄位需包含 '成分名 (日)')", type=['csv'])

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    st.write("### 原始資料預覽")
    st.dataframe(df.head(5))

    if st.button("啟動多層級補齊程序"):
        with st.spinner("正在執行跨資料庫檢索與翻譯..."):
            result_df = fetch_and_process_data(df.copy(), az_key, az_region)
            
            if result_df is not None:
                st.success("程序執行完畢！")
                
                # 統計數據 (修正 NameError 問題，直接使用字串)
                k_filled = result_df['KEGG_ID'].notna().sum()
                w_filled = result_df['成分名 (英)'].str.contains(r'\(Wiki\)', na=False).sum()
                a_filled = result_df['成分名 (英)'].str.contains(r'\(Azure\)', na=False).sum()
                final_miss = result_df['成分名 (英)'].isna().sum()

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("KEGG 成功數", f"{k_filled}")
                c2.metric("Wiki 翻譯數", f"{w_filled}")
                c3.metric("Azure 翻譯數", f"{a_filled}")
                c4.metric("剩餘空缺", f"{final_miss}")

                if final_miss > 0:
                    with st.expander("🔍 檢視無法自動補齊的項目"):
                        st.table(result_df[result_df['成分名 (英)'].isna()][['成分名 (日)']])

                st.subheader("處理結果")
                st.dataframe(result_df)

                # 下載
                output = io.BytesIO()
                result_df.to_csv(output, index=False, encoding='utf-8-sig')
                st.download_button("📥 下載修正後的 CSV", data=output.getvalue(), file_name="Drug_List_Full_Updated.csv")
