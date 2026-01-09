import streamlit as st
import pandas as pd
import pdfplumber
import requests
import time
import io

# --- 1. 功能函數定義 ---

def get_kegg_info(drug_name_jp):
    """查詢 KEGG API 獲取英文名與 ID"""
    try:
        # 去掉括號內容以提高匹配率 (例如: ワルファリンカリウム -> ワルファリン)
        clean_name = drug_name_jp.split('(')[0].split('（')[0].strip()
        search_url = f"https://rest.kegg.jp/find/drug/{clean_name}"
        res = requests.get(search_url, timeout=5)
        if res.status_code == 200 and res.text.strip():
            first_line = res.text.split('\n')[0].split('\t')
            kegg_id = first_line[0].replace('dr:', '')
            
            # 獲取詳細名稱
            info_url = f"https://rest.kegg.jp/get/{kegg_id}"
            info_res = requests.get(info_url, timeout=5)
            eng_name = "N/A"
            for line in info_res.text.split('\n'):
                if line.startswith('NAME'):
                    eng_name = line.replace('NAME', '').strip().split(';')[0]
                    break
            return kegg_id, eng_name
    except:
        pass
    return "N/A", "N/A"

def translate_with_azure_logic(text):
    """
    此處模擬 Azure 翻譯邏輯。
    實際使用請替換為 requests.post(azure_endpoint, ...)
    """
    # 簡易醫學術語對照表
    mapping = {
        "継続成分": "持續成分", "新規成分": "新成分",
        "内": "內服", "注": "注射", "外": "外用",
        "血液凝固阻止剤": "抗凝血劑", "全身麻酔剤": "全身麻醉劑",
        "催眠鎮静剤": "催眠鎮靜劑", "選定理由概要": "選定理由摘要"
    }
    for k, v in mapping.items():
        text = text.replace(k, v)
    return text

# --- 2. Streamlit 介面 ---

st.title("藥品清單解析與 KEGG 對照工具")
st.info("上傳 PDF 後，系統將自動解析表格並對接 KEGG 資料庫。")

uploaded_file = st.file_uploader("上傳 PDF 檔案", type="pdf")

if uploaded_file is not None:
    try:
        with st.spinner('正在解析 PDF 並查詢 KEGG API...'):
            raw_rows = []
            with pdfplumber.open(uploaded_file) as pdf:
                for page in pdf.pages:
                    table = page.extract_table()
                    if table:
                        # 假設第一行為標題，從第二行開始處理
                        for row in table[1:]:
                            if row[0] is None: continue # 跳過空行
                            raw_rows.append(row)
            
            # 轉換為 DataFrame 並處理
            processed_data = []
            progress_bar = st.progress(0)
            
            for i, row in enumerate(raw_rows):
                # 確保原始數據結構正確 (根據檔案調整索引)
                # row[0]: 區分, row[1]: 途徑, row[3]: 分類名, row[4]: 成分名, row[6]: 理由
                jp_name = str(row[4]).replace('\n', '')
                
                # 執行 KEGG 對照
                k_id, en_name = get_kegg_info(jp_name)
                
                # 整合資料
                processed_data.append({
                    "區分": translate_with_azure_logic(row[0]),
                    "給藥途徑": translate_with_azure_logic(row[1]),
                    "藥效分類": translate_with_azure_logic(row[3]),
                    "成分名 (日)": jp_name,
                    "成分名 (英)": en_name,
                    "KEGG_ID": k_id,
                    "選定理由摘要": translate_with_azure_logic(row[6]),
                    "R7年度分類案": row[7]
                })
                # 更新進度條
                progress_bar.progress((i + 1) / len(raw_rows))
            
            final_df = pd.DataFrame(processed_data)
            
            st.success("處理完成！")
            st.dataframe(final_df)

            # CSV 下載按鈕
            csv = final_df.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                label="下載完整 CSV 檔案",
                data=csv,
                file_name="drug_list_kegg_translated.csv",
                mime="text/csv",
            )
            
    except Exception as e:
        st.error(f"執行出錯: {e}")
