import streamlit as st
import pdfplumber
import pandas as pd
import requests
import re
import time
import io
from urllib.parse import quote
from bs4 import BeautifulSoup

# --- 1. 設定區域 (Azure 翻譯) ---
AZURE_KEY = "9JDF24qrsW8rXiYmChS17yEPyNRI96nNXXqEKn5CyI6ql6iYcTOFJQQJ99BLAC3pKaRXJ3w3AAAbACOGVYVU"
AZURE_ENDPOINT = "https://api.cognitive.microsofttranslator.com"
AZURE_REGION = "eastasia"

# --- 2. 核心功能函式 ---

def fetch_japic_en_name(jp_name):
    """
    沿用您的邏輯：從 KEGG/Japic 抓取英文成分名
    """
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64) AppleWebKit/537.36"}
    # 清理日文名稱，只取核心片假名
    raw_clean = re.split(r'[\(\n\s（]', str(jp_name))[0].strip()
    katakana_match = re.match(r'^[\u30A0-\u30FF\u30FB\u30FC]+', raw_clean)
    search_keyword = katakana_match.group(0) if katakana_match else raw_clean
    
    if len(search_keyword) < 2: return "[格式不符]"

    try:
        search_url = f"https://www.kegg.jp/medicus-bin/search_drug?search_keyword={quote(search_keyword)}"
        r_s = requests.get(search_url, headers=headers, timeout=10)
        codes = re.findall(r'japic_code=(\d+)', r_s.text + r_s.url)
        
        if codes:
            jid = codes[0].zfill(8)
            ri = requests.get(f"https://www.kegg.jp/medicus-bin/japic_med?japic_code={jid}", headers=headers)
            ri.encoding = ri.apparent_encoding
            i_soup = BeautifulSoup(ri.text, 'html.parser')
            th = i_soup.find('th', string=re.compile(r'欧文一般名'))
            if th and th.find_next_sibling('td'):
                return th.find_next_sibling('td').get_text(strip=True)
    except: pass
    return "[未檢出]"

def parse_medicine_pdf(file):
    """
    解析 PDF 表格並提取：給藥方式、用途類別、成分名
    """
    all_rows = []
    current_cat = "未知類別"
    
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            # 類別判定邏輯
            if "(1)" in text or "カテゴリA" in text: current_cat = "Category A (最優先)"
            elif "(2)" in text or "カテゴリB" in text: current_cat = "Category B (優先)"
            elif "(3)" in text or "カテゴリC" in text: current_cat = "Category C (一般)"

            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    # 根據 PDF 結構，row[0]=給藥方式, row[1]=編號, row[2]=日文名
                    if not row or len(row) < 3: continue
                    route = str(row[0]).strip().replace('\n', '')
                    class_no = str(row[1]).strip().replace('\n', '')
                    name_jp = str(row[2]).strip().replace('\n', ' ')

                    # 過濾有效資料行（給藥方式通常為 內、注、外）
                    if route in ['内', '注', '外']:
                        all_rows.append({
                            "類別": current_cat,
                            "給藥方式": route,
                            "用途類別 (編號)": class_no,
                            "成分日文名": name_jp
                        })
    return pd.DataFrame(all_rows)

# --- 3. Streamlit UI ---

st.set_page_config(layout="wide", page_title="日本安定確保醫藥品對照工具")
st.title("💊 日本安定確保醫藥品解析工具")
st.info("上傳厚勞省 PDF，系統將自動解析表格並透過 KEGG 抓取英文成分名。")

uploaded_file = st.file_uploader("請上傳安定確保醫藥品 PDF 檔案", type=['pdf'])

if uploaded_file:
    if st.button("開始解析並對照英文名"):
        # 第一步：解析 PDF
        with st.spinner("正在讀取 PDF 表格..."):
            df = parse_medicine_pdf(uploaded_file)
        
        if not df.empty:
            st.success(f"成功解析 {len(df)} 項藥品，開始進行 KEGG 英文名對照...")
            
            # 第二步：對照英文名
            results = []
            progress_bar = st.progress(0)
            
            for i, row in df.iterrows():
                # 呼叫您提供的對照邏輯
                en_name = fetch_japic_en_name(row["成分日文名"])
                
                results.append({
                    "類別": row["類別"],
                    "給藥方式": row["給藥方式"],
                    "用途類別": row["用途類別 (編號)"],
                    "成分日文名": row["成分日文名"],
                    "成分英文名": en_name
                })
                
                # 更新進度條
                progress_bar.progress((i + 1) / len(df))
                # 避免頻繁請求被封鎖
                if i % 5 == 0: time.sleep(0.2)
            
            final_df = pd.DataFrame(results)
            st.dataframe(final_df, use_container_width=True)
            
            # 下載成果
            csv = final_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 下載對照列表 (CSV)", csv, "Japan_Medicine_List.csv", "text/csv")
        else:
            st.error("未能識別 PDF 中的表格內容。")
