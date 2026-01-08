import streamlit as st
import pdfplumber
import pandas as pd
import requests
import re
import time
import io
from urllib.parse import quote
from bs4 import BeautifulSoup

# --- 1. 設定區域 (Azure 憑據) ---
AZURE_KEY = "9JDF24qrsW8rXiYmChS17yEPyNRI96nNXXqEKn5CyI6ql6iYcTOFJQQJ99BLAC3pKaRXJ3w3AAAbACOGVYVU"
AZURE_ENDPOINT = "https://api.cognitive.microsofttranslator.com"
AZURE_REGION = "eastasia"

# --- 2. 核心對照邏輯：Azure 優先 ➔ KEGG 補底 ---
def get_english_name_strict(jp_name):
    """
    嚴格邏輯：
    1. 嘗試 Azure 翻譯
    2. 若 Azure 回傳為空或出錯，則啟動 KEGG 爬蟲
    """
    if not jp_name or len(str(jp_name)) < 2:
        return "N/A", "Skip"

    # 清理日文名稱（移除劑型括號）
    clean_ja = re.split(r'[\(\n\s（]', str(jp_name))[0].strip()
    
    # --- Step 1: Azure Translator ---
    try:
        url = f"{AZURE_ENDPOINT.strip('/')}/translate?api-version=3.0&from=ja&to=en"
        headers = {
            'Ocp-Apim-Subscription-Key': AZURE_KEY,
            'Ocp-Apim-Subscription-Region': AZURE_REGION,
            'Content-type': 'application/json; charset=utf-8'
        }
        res = requests.post(url, headers=headers, json=[{'text': clean_ja}], timeout=8)
        if res.status_code == 200:
            en_result = res.json()[0]['translations'][0]['text']
            if en_result and len(en_result) > 2:
                return en_result, "Azure"
    except:
        pass

    # --- Step 2: KEGG Medicus (當 Azure 失敗時) ---
    try:
        search_url = f"https://www.kegg.jp/medicus-bin/search_drug?search_keyword={quote(clean_ja)}"
        r_s = requests.get(search_url, timeout=10)
        codes = re.findall(r'japic_code=(\d+)', r_s.text + r_s.url)
        if codes:
            jid = codes[0].zfill(8)
            ri = requests.get(f"https://www.kegg.jp/medicus-bin/japic_med?id={jid}")
            ri.encoding = ri.apparent_encoding
            soup = BeautifulSoup(ri.text, 'html.parser')
            th = soup.find('th', string=re.compile(r'欧文一般名'))
            if th and th.find_next_sibling('td'):
                return th.find_next_sibling('td').get_text(strip=True), "KEGG"
    except:
        pass

    return "[對照失敗]", "None"

# --- 3. 錨點定標解析函式 (已校準至 505+ 項) ---
def parse_pdf_with_anchors(file):
    all_data = []
    current_cat = "未知類別"
    
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            # 類別判定
            if "(1)" in text: current_cat = "Cat A (最優先)"
            elif "(2)" in text: current_cat = "Cat B (優先)"
            elif "(3)" in text: current_cat = "Cat C (穩定確保)"

            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                if not line or "成分名" in line: continue
                
                # 您的錨點邏輯：(給藥方式) (3位用途編號) (成分名)
                match = re.search(r'^(内|注|外)\s*(\d{3})\s*(.+)$', line)
                
                if match:
                    route, code, name = match.groups()
                    all_data.append({
                        "類別": current_cat,
                        "給藥方式": route,
                        "用途類別": code,
                        "成分日文名": name.strip()
                    })
                else:
                    # 跨行合併邏輯：將斷行的藥名接回上一筆
                    if all_data and not re.match(r'^\d+$', line):
                        if len(line) > 1 and "厚生労働省" not in line:
                            all_data[-1]["成分日文名"] += line.strip()

    # 清洗數據
    for item in all_data:
        # 移除可能夾雜的雜訊
        item["成分日文名"] = re.sub(r'\s+', '', item["成分日文名"])
        item["成分日文名"] = re.sub(r'\d+$', '', item["成分日文名"])
    
    return pd.DataFrame(all_data)

# --- 4. Streamlit UI 介面 ---
st.set_page_config(layout="wide", page_title="藥品 506 項全解析")
st.title("💊 安定確保醫藥品全量解析 (Azure 優先版)")
st.info("當前邏輯：錨點定標掃描 ➔ Azure 翻譯 ➔ KEGG 補底對照")

f = st.file_uploader("上傳 PDF (000785498.pdf)", type=['pdf'])

if f:
    if 'final_df' not in st.session_state:
        st.session_state.raw_list = parse_pdf_with_anchors(f)
    
    df = st.session_state.raw_list
    st.success(f"✅ 成功提取 {len(df)} 項成分！")
    st.dataframe(df, use_container_width=True)

    if st.button("🚀 開始執行全量 505 項翻譯對照"):
        results = []
        bar = st.progress(0)
        status = st.empty()
        
        for i, row in df.iterrows():
            jp_name = row["成分日文名"]
            status.text(f"正在對照 ({i+1}/{len(df)}): {jp_name}")
            
            # 執行嚴格對照邏輯
            en_name, source = get_english_name_strict(jp_name)
            
            results.append({
                "類別": row["類別"],
                "給藥方式": row["給藥方式"],
                "用途類別": row["用途類別"],
                "成分日文名": jp_name,
                "成分英文名": en_name,
                "對照來源": source
            })
            bar.progress((i + 1) / len(df))
            if i % 15 == 0: time.sleep(0.1)
            
        st.session_state.result_df = pd.DataFrame(results)
        st.success("🎉 全量對照完成！")
        st.dataframe(st.session_state.result_df, use_container_width=True)
        
        # 下載 Excel
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
            st.session_state.result_df.to_excel(writer, index=False)
        st.download_button("📥 下載全解析報告 (Excel)", out.getvalue(), "Medicine_Full_Report.xlsx")
