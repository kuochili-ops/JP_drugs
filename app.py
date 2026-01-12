import streamlit as st
import pandas as pd
import requests
import re

# --- 1. 頁面配置 ---
st.set_page_config(page_title="KEGG 全檔案對照補完", layout="wide")

# --- 2. 獲取 KEGG 完整字典 (快取以提升速度) ---
@st.cache_data(ttl=86400)
def fetch_kegg_master_list():
    url = "https://rest.kegg.jp/list/drug_ja/"
    kegg_map = {}
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            lines = response.text.strip().split('\n')
            for line in lines:
                parts = line.split('\t')
                if len(parts) >= 2:
                    k_id = parts[0].strip() # 例如 dr:D00001
                    full_name = parts[1]
                    # 解析 "日文名; 英文名 [其他]"
                    if ';' in full_name:
                        jp_name, rest = full_name.split(';', 1)
                        en_name = rest.split('[')[0].strip()
                        
                        # 處理比對用的 Key：移除括號內容與空格
                        clean_key = re.sub(r'[\(\（].*?[\)\）]', '', jp_name).replace(' ', '').strip()
                        kegg_map[clean_key] = {"id": k_id, "en": en_name}
        return kegg_map
    except Exception as e:
        st.error(f"連線 KEGG 失敗: {e}")
        return {}

# --- 3. UI 邏輯 ---
st.title("🧪 KEGG 全量資料對照補完 (763 筆完整處理)")
st.info("本程式將移除所有數量限制，針對 CSV 內所有項目進行英文名與 ID 比對。")

uploaded_file = st.file_uploader("上傳您整合後的 CSV (Final_Drug_List_Merged.csv)", type="csv")

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    total_rows = len(df)
    
    if st.button(f"開始全量比對 (共 {total_rows} 筆資料)"):
        with st.spinner("正在加載 KEGG 最新藥典..."):
            kegg_master = fetch_kegg_master_list()
        
        if kegg_master:
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # 遍歷所有列，不設 head() 限制
            for i in range(total_rows):
                raw_jp = str(df.at[i, '成分名 (日)']).strip()
                
                # 預處理對照用的日文 Key
                # 1. 移除 (JP18), (局) 等括號內容
                # 2. 移除 "水和物" 以增加匹配成功率
                match_key = re.sub(r'[\(\（].*?[\)\）]', '', raw_jp)
                match_key = match_key.replace('水和物', '').replace(' ', '').strip()
                
                if match_key in kegg_master:
                    df.at[i, 'KEGG_ID'] = kegg_master[match_key]['id']
                    df.at[i, '成分名 (英)'] = kegg_master[match_key]['en']
                
                # 每 20 筆更新進度介面
                if i % 20 == 0 or i == total_rows - 1:
                    progress_bar.progress((i + 1) / total_rows)
                    status_text.text(f"進度: {i+1} / {total_rows} | 正在處理: {match_key}")

            st.success(f"✅ 全數 {total_rows} 筆資料比對完成！")
            
            # 顯示結果預覽 (這裡顯示 50 筆供確認，但下載的是全部)
            st.subheader("比對結果預覽 (前 50 筆)")
            st.dataframe(df[['成分名 (日)', '成分名 (英)', 'KEGG_ID', '翻譯理由']].head(50), use_container_width=True)

            # 生成下載連結
            csv_final = df.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                label="📥 下載最終完整對照補完檔案 (CSV)",
                data=csv_final,
                file_name="Final_Drug_List_All_763.csv",
                mime="text/csv"
            )
