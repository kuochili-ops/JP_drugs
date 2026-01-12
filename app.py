import streamlit as st
import pandas as pd
import requests
import re
import time

st.set_page_config(page_title="KEGG 藥品名補完工具", layout="wide")

# --- 1. KEGG 字典抓取函數 ---
@st.cache_data(ttl=3600)
def get_kegg_dictionary():
    url = "https://rest.kegg.jp/list/drug_ja/"
    kegg_dict = {}
    try:
        response = requests.get(url, timeout=20)
        if response.status_code == 200:
            for line in response.text.strip().split('\n'):
                parts = line.split('\t')
                if len(parts) >= 2:
                    k_id = parts[0].replace('dr:', '').strip()
                    full_name = parts[1]
                    # KEGG 格式通常是: 日文名; 英文名 [其他資訊]
                    if ';' in full_name:
                        jp_part, en_part = full_name.split(';', 1)
                        # 清理括號
                        clean_jp = re.sub(r'[\(\（].*?[\)\）]', '', jp_part).strip()
                        clean_en = re.sub(r'[\(\（].*?[\)\）]', '', en_part).strip()
                        kegg_dict[clean_jp] = {"id": f"dr:{k_id}", "en": clean_en}
        return kegg_dict
    except Exception as e:
        st.error(f"無法連線至 KEGG API: {e}")
        return {}

# --- 2. UI 介面 ---
st.title("🧪 KEGG API 藥品英文名與 ID 自動對照")
st.info("系統將根據『成分名 (日)』自動對比 KEGG 資料庫，補完『成分名 (英)』與『KEGG_ID』。")

uploaded_file = st.file_uploader("上傳已整合的 CSV (Final_Drug_List_Merged.csv)", type="csv")

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    
    if st.button("🔍 開始對照補完"):
        kegg_data = get_kegg_dictionary()
        
        progress_bar = st.progress(0)
        status = st.empty()
        
        # 轉換為清單加速處理
        total = len(df)
        for i, row in df.iterrows():
            raw_jp = str(row['成分名 (日)']).strip()
            # 移除日文名中的括號以便對照，例如：ワルファリンカリウム(JP18) -> ワルファリンカリウム
            clean_jp = re.sub(r'[（\(].*?[）\)]', '', raw_jp).strip()
            
            if clean_jp in kegg_data:
                df.at[i, 'KEGG_ID'] = kegg_data[clean_jp]['id']
                df.at[i, '成分名 (英)'] = kegg_data[clean_jp]['en']
            
            if i % 20 == 0 or i == total - 1:
                progress_bar.progress((i + 1) / total)
                status.text(f"對照中: {clean_jp}")

        st.success("✅ 對照補完完成！")
        st.dataframe(df[['成分名 (日)', '成分名 (英)', 'KEGG_ID', '翻譯理由']].head(10))

        # 下載最終結果
        final_csv = df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label="📥 下載對照補完後檔案",
            data=final_csv,
            file_name="Final_Drug_List_Full_Complete.csv",
            mime="text/csv"
        )
