import streamlit as st
import pandas as pd
import requests
import re

# --- 1. 配置與頁面設定 ---
st.set_page_config(page_title="KEGG 全檔案自動對照", layout="wide")

# --- 2. 核心：抓取 KEGG 完整字典 ---
@st.cache_data(ttl=86400) # 快取一天，避免重複請求
def fetch_full_kegg_dict():
    url = "https://rest.kegg.jp/list/drug_ja/"
    kegg_map = {}
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            lines = response.text.strip().split('\n')
            for line in lines:
                parts = line.split('\t')
                if len(parts) >= 2:
                    # ID 格式處理 (dr:D00001 -> dr:D00001)
                    k_id = parts[0].strip()
                    full_name = parts[1]
                    # 分解 日文; 英文 [其他]
                    if ';' in full_name:
                        jp_name, rest = full_name.split(';', 1)
                        en_name = rest.split('[')[0].strip() # 移除括號內的註解
                        
                        # 清理日文名括號，建立對照 Key
                        clean_jp_key = re.sub(r'[\(\（].*?[\)\）]', '', jp_name).strip()
                        kegg_map[clean_jp_key] = {"id": k_id, "en": en_name}
        return kegg_map
    except Exception as e:
        st.error(f"連線 KEGG API 失敗: {e}")
        return {}

# --- 3. UI 介面 ---
st.title("🧪 KEGG 全檔案自動比對系統")
st.info("系統將自動抓取 KEGG 最新資料庫，並對全數 763 筆項目進行英文名與 ID 補完。")

uploaded_file = st.file_uploader("上傳您整合後的 CSV (Final_Drug_List_Merged.csv)", type="csv")

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    total_count = len(df)
    
    if st.button(f"🚀 開始全量比對 (共 {total_count} 筆)"):
        # 抓取字典
        with st.spinner("正在從 KEGG 伺服器獲取完整藥典..."):
            kegg_master = fetch_full_kegg_dict()
        
        if not kegg_master:
            st.error("無法取得 KEGG 字典，請稍後再試。")
        else:
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # 開始全量迴圈
            for i, row in df.iterrows():
                # 取得原始日文名
                raw_jp = str(row['成分名 (日)']).strip()
                
                # 【關鍵】清理比對用的 Key (例如移除 (JP18), 水和物 等)
                clean_jp = re.sub(r'[\(\（].*?[\)\）]', '', raw_jp)
                clean_jp = clean_jp.replace('水和物', '').strip()
                
                # 進行比對
                if clean_jp in kegg_master:
                    df.at[i, 'KEGG_ID'] = kegg_master[clean_jp]['id']
                    df.at[i, '成分名 (英)'] = kegg_master[clean_jp]['en']
                
                # 更新進度
                if i % 20 == 0 or i == total_count - 1:
                    progress_bar.progress((i + 1) / total_count)
                    status_text.text(f"進度: {i+1}/{total_count} | 正在比對: {clean_jp}")

            st.success(f"✅ 全檔案 {total_count} 筆對照完成！")
            
            # 顯示前幾筆結果確認
            st.subheader("比對結果預覽")
            st.dataframe(df[['成分名 (日)', '成分名 (英)', 'KEGG_ID']].head(20), use_container_width=True)

            # 提供下載
            csv_final = df.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                label="📥 下載最終完整對照 CSV",
                data=csv_final,
                file_name="Final_Drug_List_Full_Matched.csv",
                mime="text/csv"
            )
