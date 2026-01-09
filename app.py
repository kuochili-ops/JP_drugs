import streamlit as st
import pandas as pd
import requests
import re

# 1. 確保 Streamlit 頁面設定
st.set_page_config(page_title="藥品清單補完工具", layout="wide")

# 2. 強化版字典抓取：精確切分分號後面的英文
@st.cache_data(ttl=3600)
def get_kegg_master_dict():
    url = "https://rest.kegg.jp/list/drug_ja/"
    kegg_map = {}
    try:
        response = requests.get(url, timeout=20)
        if response.status_code == 200:
            lines = response.text.strip().split('\n')
            for line in lines:
                parts = line.split('\t')
                if len(parts) >= 2:
                    # 格式如 dr:D01280
                    k_id = parts[0].replace('dr:', '').strip()
                    full_text = parts[1]
                    
                    # 邏輯：ワルファリンカリウム (JP18); Warfarin potassium (JP18)
                    if ';' in full_text:
                        # 抓分號後面的英文
                        en_part = full_text.split(';')[1].strip()
                        en_name = re.sub(r'[\(\（].*?[\)\）]', '', en_part).strip()
                        
                        # 抓分號前的日文作為比對 Key
                        jp_part = full_text.split(';')[0].strip()
                        jp_name = re.sub(r'[\(\（].*?[\)\）]', '', jp_part).strip()
                        
                        kegg_map[jp_name] = {"id": k_id, "en": en_name}
        return kegg_map
    except Exception as e:
        st.error(f"KEGG 字典讀取異常: {e}")
        return {}

# 3. 翻譯術語表
TERM_MAP = {
    "他に分類されない代謝性医薬品": "其他類別代謝藥物",
    "血液凝固阻止剤": "抗凝血劑",
    "薬効分類名": "藥效分類名稱",
    "選定理由概要": "選定理由摘要",
    "継続成分": "持續成分",
    "新規成分": "新成分",
    "内": "內服", "注": "注射", "外": "外用"
}

st.title("💊 藥品資料修正與 KEGG 對照")

# 立即執行字典抓取
kegg_lookup = get_kegg_master_dict()

# 檢查字典是否抓到資料 (避免畫面白屏)
if not kegg_lookup:
    st.warning("⚠️ 正在嘗試從 KEGG 伺服器獲取資料，請稍候或重新整理。")

uploaded_file = st.file_uploader("請上傳您的 CSV 檔案", type="csv")

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    
    # 強制初始化欄位，避免欄位「不見」
    if 'KEGG_ID' not in df.columns:
        df['KEGG_ID'] = "Searching..."
    if '成分名 (英)' not in df.columns:
        df['成分名 (英)'] = "Searching..."

    if st.button("開始執行精確對照"):
        with st.spinner('正在比對 KEGG 數據庫...'):
            for i, row in df.iterrows():
                # 清理 CSV 中的日文名 (移除括號與換行)
                raw_name = str(row['成分名 (日)']).replace('\n', '').strip()
                clean_name = re.sub(r'[（\(].*?[）\)]', '', raw_name).strip()

                # A. 比對字典
                if clean_name in kegg_lookup:
                    df.at[i, 'KEGG_ID'] = kegg_lookup[clean_name]['id']
                    df.at[i, '成分名 (英)'] = kegg_lookup[clean_name]['en']
                else:
                    df.at[i, 'KEGG_ID'] = "Not Found"
                    df.at[i, '成分名 (英)'] = "N/A"

                # B. 翻譯替換
                for col in df.columns:
                    val = str(df.at[i, col])
                    for jp, tw in TERM_MAP.items():
                        if jp in val:
                            val = val.replace(jp, tw)
                    df.at[i, col] = val

            st.success("✅ 處理完成")
            st.dataframe(df, use_container_width=True)

            # 下載功能
            csv_out = df.to_csv(index=False, encoding="utf-8-sig")
            st.download_button("📥 下載修正後的 CSV", csv_out, "final_drugs.csv", "text/csv")
