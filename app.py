import streamlit as st
import pandas as pd
import requests
import re
from urllib.parse import quote

def fetch_kegg_english(japanese_name):
    """
    直接請求日本 KEGG 權威數據庫進行對照
    """
    if not japanese_name or pd.isna(japanese_name):
        return "N/A"

    # 清除日文括號備註 (如品牌名)
    clean_ja = re.sub(r'[\(\（].*?[\)\）]', '', str(japanese_name)).strip()
    
    # 對於複合藥，拆分後分別請求
    if '･' in clean_ja or '・' in clean_ja:
        parts = re.split(r'[･・]', clean_ja)
        return " / ".join([fetch_kegg_english(p) for p in parts])

    try:
        # 外部資源：KEGG API (日本最權威藥物數據庫)
        # 步驟 1: 搜尋藥物日文名對應的 KEGG 藥物編號 (D編號)
        search_url = f"https://rest.kegg.jp/find/drug/{quote(clean_ja)}"
        response = requests.get(search_url, timeout=5)
        
        if response.status_code == 200 and response.text.strip():
            # 獲取第一個匹配的 D 編號
            kegg_id = response.text.split('\t')[0].replace('dr:', '')
            
            # 步驟 2: 獲取該編號的詳細資訊 (包含英文名)
            info_url = f"https://rest.kegg.jp/get/{kegg_id}"
            info_resp = requests.get(info_url, timeout=5)
            
            if info_resp.status_code == 200:
                # 在回傳文本中尋找 "NAME" 欄位下的英文部分
                lines = info_resp.text.split('\n')
                for line in lines:
                    if line.startswith('NAME'):
                        # 格式通常是: NAME  Japanese (English)
                        match = re.search(r'\((.*?)\)', line)
                        if match:
                            return match.group(1).split(';')[0].strip()
        
        # 備援機制：如果 KEGG 沒抓到，標記為需核對
        return f"[未查獲] {clean_ja}"

    except Exception:
        return f"[連線超時] {clean_ja}"

# --- UI ---
st.set_page_config(layout="wide")
st.title("🛡️ KEGG 日本官方數據庫：505項全量對照")
st.markdown("此版本直接串接 **KEGG (Kyoto Encyclopedia of Genes and Genomes)**，是目前識別日文藥名最精準的外部資源。")

f = st.file_uploader("上傳 CSV 檔案", type=['csv'])

if f:
    df = pd.read_csv(f)
    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
    
    if st.button("🚀 啟動 KEGG 數據庫檢索"):
        with st.spinner('正在連線至日本 KEGG 伺服器...'):
            # 執行對照
            df['成分英文名'] = df['成分日文名'].apply(fetch_kegg_english)
            df['來源'] = "External_KEGG_Official"
            
        st.success("✅ 檢索完成！")
        st.dataframe(df, use_container_width=True)
        
        csv_data = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下載 KEGG 對照完成版", csv_data, "Medicine_KEGG_Result.csv")
