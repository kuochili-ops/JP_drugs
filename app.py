import streamlit as st
import pdfplumber
import pandas as pd
import requests
import re
import time
import io
from urllib.parse import quote
from bs4 import BeautifulSoup

# --- 1. 設定區域 ---
AZURE_KEY = "9JDF24qrsW8rXiYmChS17yEPyNRI96nNXXqEKn5CyI6ql6iYcTOFJQQJ99BLAC3pKaRXJ3w3AAAbACOGVYVU"
AZURE_ENDPOINT = "https://api.cognitive.microsofttranslator.com"
AZURE_REGION = "eastasia"

# --- 2. 翻譯與對照核心邏輯 (嚴格執行 Azure 優先) ---

def get_english_name_logic(jp_name):
    """
    邏輯：1. Azure 翻譯 -> 2. 失敗則 KEGG 爬蟲
    """
    if not jp_name or str(jp_name).lower() == 'none':
        return "N/A", "Skip"

    # --- Step 1: Azure 翻譯 ---
    try:
        clean_ja = re.split(r'[\(\n\s（]', str(jp_name))[0].strip()
        url = f"{AZURE_ENDPOINT.strip('/')}/translate?api-version=3.0&from=ja&to=en"
        headers = {
            'Ocp-Apim-Subscription-Key': AZURE_KEY,
            'Ocp-Apim-Subscription-Region': AZURE_REGION,
            'Content-type': 'application/json; charset=utf-8'
        }
        res = requests.post(url, headers=headers, json=[{'text': clean_ja}], timeout=8)
        if res.status_code == 200:
            en_res = res.json()[0]['translations'][0]['text']
            if en_res and len(en_res) > 2:
                return en_res, "Azure"
    except:
        pass

    # --- Step 2: KEGG 爬蟲 (Azure 沒拿到結果時) ---
    try:
        search_kw = re.split(r'[\(\n\s（]', str(jp_name))[0].strip()
        search_url = f"https://www.kegg.jp/medicus-bin/search_drug?search_keyword={quote(search_kw)}"
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

    return "[翻譯失敗]", "None"

# --- 3. 解析函式 (修正漏抓 506 項的問題) ---

def parse_full_medicine_pdf(file):
    all_data = []
    current_cat = "未知類別"
    
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            
            # 1. 判定類別
            if "(1)" in text: current_cat = "Cat A"
            elif "(2)" in text: current_cat = "Cat B"
            elif "(3)" in text: current_cat = "Cat C"

            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                if not line or "成分名" in line: continue
                
                # 核心 Regex：匹配 (給藥方式) (3位編號) (成分名)
                match = re.search(r'^(内|注|外)\s*(\d{3})\s*(.+)$', line)
                
                if match:
                    # 發現新藥項：建立紀錄
                    route, code, name = match.groups()
                    all_data.append({
                        "類別": current_cat,
                        "給藥方式": route,
                        "用途類別": code,
                        "成分日文名": name.strip()
                    })
                else:
                    # 跨行處理：如果這行不符合錨點，但我們已經有上一筆紀錄
                    # 且這行看起來不像是頁碼或標題，就合併到上一筆的成分名中
                    if all_data and not re.match(r'^\d+$', line): # 排除純頁碼行
                        # 檢查這行是否包含特定關鍵字，避免誤抓標題
                        if len(line) > 1 and "厚生労働省" not in line:
                            all_data[-1]["成分日文名"] += line.strip()

    # 最終清洗：處理合併後可能產生的重複空格或雜訊
    for item in all_data:
        item["成分日文名"] = re.sub(r'\s+', '', item["成分日文名"])
        # 移除可能誤抓到的結尾頁碼數字
        item["成分日文名"] = re.sub(r'\d+$', '', item["成分日文名"])
    
    return pd.DataFrame(all_data)
# --- 4. Streamlit UI 介面 ---
st.set_page_config(layout="wide", page_title="安定確保醫藥品 506項解析")
st.title("💊 安定確保醫藥品全量解析工具")
st.write("解析邏輯：PDF 表格+文字掃描 (506項) -> Azure 優先翻譯 -> KEGG 備援")

f = st.file_uploader("請上傳 PDF (000785498.pdf)", type=['pdf'])

if f:
    if 'raw_df' not in st.session_state:
        with st.spinner("正在提取 506 項成分清單..."):
            # 呼叫修正後的函式名
            st.session_state.raw_df = parse_full_medicine_pdf(f)
    
    df = st.session_state.raw_df
    st.success(f"✅ 成功提取 {len(df)} 項成分！")
    st.dataframe(df, use_container_width=True)

    if st.button("🚀 開始全量對照 (Azure + KEGG)"):
        final_list = []
        bar = st.progress(0)
        status = st.empty()
        
        for i, row in df.iterrows():
            jp_name = row["成分日文名"]
            status.text(f"處理進度 ({i+1}/{len(df)}): {jp_name}")
            
            # 執行翻譯邏輯
            en_name, source = get_english_name_logic(jp_name)
            
            final_list.append({
                "類別": row["類別"],
                "給藥方式": row["給藥方式"],
                "用途類別": row["用途類別"],
                "成分日文名": jp_name,
                "成分英文名": en_name,
                "翻譯來源": source
            })
            bar.progress((i + 1) / len(df))
            
            # 緩衝
            if i % 15 == 0: time.sleep(0.1)
            
        res_df = pd.DataFrame(final_list)
        st.success("🎉 全量對照完成！")
        st.dataframe(res_df, use_container_width=True)
        
        # 下載 Excel
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
            res_df.to_excel(writer, index=False)
        st.download_button("📥 下載全解析 Excel 報告", out.getvalue(), "Medicine_Full_Report.xlsx")
