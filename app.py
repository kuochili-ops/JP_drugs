import streamlit as st
import pandas as pd
import requests
import re
import io

# 設定網頁標題
st.set_page_config(page_title="藥品清單 KEGG 精確對照", layout="wide")

# --- 1. 強化版 KEGG 字典解析 ---
@st.cache_data(ttl=3600)
def get_kegg_master_dict():
    url = "https://rest.kegg.jp/list/drug_ja/"
    kegg_map = {}
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            for line in response.text.strip().split('\n'):
                parts = line.split('\t')
                if len(parts) >= 2:
                    k_id = parts[0].replace('dr:', '')
                    full_text = parts[1]
                    
                    # 處理邏輯：
                    # 例：ワルファリンカリウム (JP18); Warfarin potassium (JP18)
                    
                    # A. 抓取分號後的英文部分
                    if ';' in full_text:
                        en_part = full_text.split(';')[1].strip()
                        # 移除英文中的 (JP18), (USP) 等括號標記
                        en_name = re.sub(r'[\(\（].*?[\)\）]', '', en_part).strip()
                        
                        # B. 抓取分號前的日文部分作為比對 Key
                        jp_part = full_text.split(';')[0].strip()
                        # 移除日文中的 (JP18) 標記以便比對
                        jp_name = re.sub(r'[\(\（].*?[\)\）]', '', jp_part).strip()
                        
                        kegg_map[jp_name] = {"id": k_id, "en": en_name}
        return kegg_map
    except Exception as e:
        return {"error": str(e)}

# --- 2. 醫學術語手動對照 (翻譯補強) ---
TERM_MAP = {
    "他に分類されない代謝性医薬品": "其他類別代謝藥物",
    "血液凝固阻止剤": "抗凝血劑",
    "全身麻酔剤": "全身麻醉劑",
    "催眠鎮静剤": "催眠鎮靜劑",
    "精神神経用剤": "精神神經用藥",
    "骨格筋弛緩剤": "骨骼肌鬆弛劑",
    "薬効分類名": "藥效分類名稱",
    "選定理由概要": "選定理由摘要",
    "継続成分": "持續成分",
    "新規成分": "新成分",
    "内": "內服", "注": "注射", "外": "外用",
    "水和物": "水合物"
}

# --- 3. UI 介面邏輯 ---
st.title("💊 藥品資料精確對照工具")
st.markdown("針對日文成分名自動對標 **KEGG ID** 與 **標準英文名**，並補完翻譯。")

# 預載字典
kegg_lookup = get_kegg_master_dict()
if "error" in kegg_lookup:
    st.error(f"KEGG 連線失敗: {kegg_lookup['error']}")

uploaded_file = st.file_uploader("1. 請上傳原始 CSV 檔案", type="csv")

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    st.write("📄 檔案預覽 (前 5 筆)：")
    st.dataframe(df.head(), use_container_width=True)
    
    if st.button("2. 開始執行精確比對與補完翻譯"):
        progress_bar = st.progress(0)
        status = st.empty()
        
        # 確保目標欄位存在
        if 'KEGG_ID' not in df.columns: df['KEGG_ID'] = "N/A"
        if '成分名 (英)' not in df.columns: df['成分名 (英)'] = "N/A"

        total = len(df)
        for i, row in df.iterrows():
            # A. 取得原始日文名並清理
            raw_name = str(row['成分名 (日)']).replace('\n', '').strip()
            # 移除「水和物」或「JP18」等括號內容進行精準比對
            clean_name = re.sub(r'[（\(].*?[）\)]', '', raw_name).strip()

            # B. 比對 KEGG 字典
            if clean_name in kegg_lookup:
                df.at[i, 'KEGG_ID'] = kegg_lookup[clean_name]['id']
                df.at[i, '成分名 (英)'] = kegg_lookup[clean_name]['en']
            
            # C. 全域日文術語翻譯替換
            for col in df.columns:
                val = str(df.at[i, col])
                for jp, tw in TERM_MAP.items():
                    if jp in val:
                        val = val.replace(jp, tw)
                df.at[i, col] = val
            
            if i % 10 == 0:
                progress_bar.progress((i + 1) / total)
                status.text(f"正在處理: {clean_name}")

        status.success("✅ 處理完成！")
        st.dataframe(df, use_container_width=True)

        # 下載按鈕
        csv_out = df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label="📥 下載最終修正版 CSV",
            data=csv_out,
            file_name="KEGG_Translated_Drugs.csv",
            mime="text/csv"
        )
