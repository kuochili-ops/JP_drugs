import streamlit as st
import pandas as pd
import requests
import urllib.parse
import re
import time

def get_official_inn_by_kegg(ja_name):
    """
    實作：URL 編碼 -> find/drug -> get/D-ID -> 提取 INN
    """
    if not ja_name or pd.isna(ja_name):
        return "N/A"

    # 清除括號備註 (如：品牌名、劑型備註)
    clean_ja = re.sub(r'[\(\（].*?[\)\）]', '', str(ja_name)).strip()
    
    # 處理複合劑 (遇到 ･ 或 ・ 自動拆分查詢)
    if '･' in clean_ja or '・' in clean_ja:
        parts = re.split(r'[･・]', clean_ja)
        return " / ".join([get_official_inn_by_kegg(p) for p in parts])

    try:
        # 1. URL 編碼
        encoded_query = urllib.parse.quote(clean_ja)
        
        # 2. 搜尋 Drug ID (find)
        find_url = f"https://rest.kegg.jp/find/drug/{encoded_query}"
        find_resp = requests.get(find_url, timeout=10)
        
        if find_resp.status_code == 200 and find_resp.text.strip():
            # 取得第一個 D 編號 (例如 dr:D00109)
            kegg_id = find_resp.text.split('\t')[0]
            
            # 3. 獲取詳細資訊 (get)
            get_url = f"https://rest.kegg.jp/get/{kegg_id}"
            get_resp = requests.get(get_url, timeout=10)
            
            if get_resp.status_code == 200:
                for line in get_resp.text.split('\n'):
                    if line.startswith('NAME'):
                        # 提取括號內的英文
                        match = re.search(r'\((.*?)\)', line)
                        if match:
                            return match.group(1).split(';')[0].strip()
                            
        return f"[Manual Check: {clean_ja}]"
    except Exception as e:
        return f"[Connection Error]"

# --- UI ---
st.set_page_config(layout="wide")
st.title("🛡️ KEGG 官方 API 對照站 - 2026 穩定版")
st.markdown("採用您提供的 **URL 編碼路徑**。建議分批處理以維持 API 穩定性。")

f = st.file_uploader("上傳您的 505 項 CSV", type=['csv'])

if f:
    df = pd.read_csv(f)
    # 清理欄位
    df = df.loc[:, ~df.columns.str.contains('^Unnamed|來源|成分英文名')]
    
    # 讓使用者選擇處理範圍（預防 API 被鎖）
    option = st.radio("選擇處理範圍：", ["全部 505 項", "僅處理前 50 項 (測試用)", "自定義範圍"])
    
    start_idx, end_idx = 0, len(df)
    if option == "僅處理前 50 項 (測試用)":
        end_idx = 50
    elif option == "自定義範圍":
        start_idx = st.number_input("起始索引", value=0)
        end_idx = st.number_input("結束索引", value=len(df))

    if st.button("🚀 開始全自動官方對照"):
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # 為了保持進度，先複製一份原始數據
        working_df = df.iloc[start_idx:end_idx].copy()
        
        for i, (idx, row) in enumerate(working_df.iterrows()):
            name = row['成分日文名']
            status_text.text(f"正在對照 ({i+1}/{len(working_df)}): {name}")
            
            en_name = get_official_inn_by_kegg(name)
            results.append(en_name)
            
            # 更新進度
            progress_bar.progress((i + 1) / len(working_df))
            
            # 💡 關鍵：每 5 筆休息一下，避免被 KEGG 視為攻擊
            if i % 5 == 0:
                time.sleep(0.3)
        
        working_df['成分英文名'] = results
        working_df['來源'] = "KEGG_Official_API"
        
        st.success("✅ 批次對照完成！")
        st.dataframe(working_df)
        
        csv_data = working_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下載此批次結果 CSV", csv_data, f"KEGG_Result_{start_idx}_{end_idx}.csv")
