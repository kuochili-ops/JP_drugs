import streamlit as st
import pandas as pd
import requests
import urllib.parse
import re
import time

def get_official_inn_by_kegg_logic(ja_name):
    """
    完全採用您提供的邏輯：URL 編碼 -> find/drug -> get/D-ID
    """
    if not ja_name or pd.isna(ja_name):
        return "N/A"

    # 1. 清洗名稱：移除括號與品牌名
    clean_ja = re.sub(r'[\(\（].*?[\)\）]', '', str(ja_name)).strip()
    
    # 處理複合劑 (･ 或 ・)
    if '･' in clean_ja or '・' in clean_ja:
        parts = re.split(r'[･・]', clean_ja)
        return " / ".join([get_official_inn_by_kegg_logic(p) for p in parts])

    try:
        # 2. 進行 URL 編碼 (如您分享的範例)
        encoded_query = urllib.parse.quote(clean_ja)
        find_url = f"https://rest.kegg.jp/find/drug/{encoded_query}"
        
        # 3. 執行 find 取得 D 編號
        find_resp = requests.get(find_url, timeout=5)
        if find_resp.status_code == 200 and find_resp.text.strip():
            # 取得第一筆 ID，例如 dr:D00109
            kegg_id = find_resp.text.split('\t')[0]
            
            # 4. 執行 get 語法獲取詳細資訊
            get_url = f"https://rest.kegg.jp/get/{kegg_id}"
            get_resp = requests.get(get_url, timeout=5)
            
            if get_resp.status_code == 200:
                # 搜尋 NAME 欄位中的英文括號
                lines = get_resp.text.split('\n')
                for line in lines:
                    if line.startswith('NAME'):
                        # 抓取括號內的英文名
                        match = re.search(r'\((.*?)\)', line)
                        if match:
                            return match.group(1).split(';')[0].strip()
        
        return f"[未查獲: {clean_ja}]"
    except Exception as e:
        return f"[連線錯誤]"

# --- Streamlit UI ---
st.set_page_config(layout="wide")
st.title("💊 505項官方對照：KEGG API 實作版")
st.info("已導入您提供的 URL 編碼與 find/drug 邏輯。")

f = st.file_uploader("上傳 505 項 CSV 檔案", type=['csv'])

if f:
    df = pd.read_csv(f)
    # 清理 DataFrame，確保沒有干擾欄位
    df = df.loc[:, ~df.columns.str.contains('^Unnamed|來源|成分英文名')]
    
    if st.button("🚀 執行全自動官方對照"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        results = []
        for i, row in df.iterrows():
            name = row['成分日文名']
            status_text.text(f"正在對照第 {i+1}/505 項: {name}")
            
            en_name = get_official_inn_by_kegg_logic(name)
            results.append(en_name)
            
            # 更新進度條
            progress_bar.progress((i + 1) / len(df))
            # 稍微延遲避免請求過快
            if i % 10 == 0: time.sleep(0.1)
            
        df['成分英文名'] = results
        df['來源'] = "KEGG_Official_API"
        
        st.success("✅ 505 項全部對照完成！")
        st.dataframe(df, use_container_width=True)
        
        csv_data = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下載官方對照版 CSV", csv_data, "Medicine_KEGG_Final.csv")
