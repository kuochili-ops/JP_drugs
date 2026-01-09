import streamlit as st
import pandas as pd
import requests
import re
import io

# --- 1. 強化版 KEGG 字典抓取 ---
@st.cache_data(ttl=3600) # 設定一小時後過期重新抓取
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
                    # 範例格式: ワルファリンカリウム (Warfarin Potassium); Warfarin ...
                    full_text = parts[1]
                    
                    # 只取分號前的主要名稱部分
                    main_part = full_text.split(';')[0].strip()
                    
                    # 使用正則：匹配 "日文名 (英文名)"
                    # 支援半形 () 與全形 （）
                    match = re.search(r'^(.+?)\s*[（\(](.+?)[）\)]', main_part)
                    
                    if match:
                        jp_name = match.group(1).strip()
                        en_name = match.group(2).strip()
                        kegg_map[jp_name] = {"id": k_id, "en": en_name}
        return kegg_map
    except Exception as e:
        return {"error": str(e)}

# --- 2. 翻譯與欄位對照表 ---
TERM_MAP = {
    "他に分類されない代謝性医薬品": "其他類別代謝藥物",
    "血液凝固阻止剤": "抗凝血劑",
    "内": "內服", "注": "注射", "外": "外用",
    "継続成分": "持續成分", "新規成分": "新成分"
}

st.title("💊 藥品資料精確對照工具")

# 初始化字典
kegg_lookup = get_kegg_master_dict()
if "error" in kegg_lookup:
    st.error(f"KEGG 字典載入失敗: {kegg_lookup['error']}")

uploaded_file = st.file_uploader("請上傳 CSV 檔案", type="csv")

if uploaded_file:
    # 讀取並顯示原始預覽
    df = pd.read_csv(uploaded_file)
    st.write("已讀取檔案，點擊下方按鈕開始處理：")
    
    if st.button("執行精確對照與翻譯"):
        with st.spinner('處理中...'):
            # 確保有這兩個欄位，若沒有則新增
            if 'KEGG_ID' not in df.columns: df['KEGG_ID'] = "N/A"
            if '成分名 (英)' not in df.columns: df['成分名 (英)'] = "N/A"

            for i, row in df.iterrows():
                # 取得原始日文名並清理換行與空白
                raw_name = str(row['成分名 (日)']).replace('\n', '').strip()
                # 移除「水和物」等括號內容再比對
                clean_name = re.sub(r'[（\(].*?[）\)]', '', raw_name)

                # A. 精確比對 KEGG
                if clean_name in kegg_lookup:
                    df.at[i, 'KEGG_ID'] = kegg_lookup[clean_name]['id']
                    df.at[i, '成分名 (英)'] = kegg_lookup[clean_name]['en']
                
                # B. 欄位翻譯補強
                for col in df.columns:
                    val = str(df.at[i, col])
                    for jp, tw in TERM_MAP.items():
                        if jp in val:
                            val = val.replace(jp, tw)
                    df.at[i, col] = val
            
            # 處理完成後強制顯示畫面
            st.success("✅ 處理完成")
            st.dataframe(df, use_container_width=True)

            # 下載按鈕
            csv_out = df.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                "📥 下載修正後的 CSV",
                csv_out,
                "final_fixed_list.csv",
                "text/csv"
            )
