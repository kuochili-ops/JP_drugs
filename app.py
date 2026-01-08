import streamlit as st
import pdfplumber
import pandas as pd
import re

# 模擬成分英文名對照表 (建議後續擴充為完整 CSV)
EN_MAPPING = {
    "ワルファリンカリウム": "Warfarin Potassium",
    "シクロスポリン": "Cyclosporine",
    "タクロリムス水和物": "Tacrolimus Hydrate",
    "プロポフォール": "Propofol",
    "ミダゾラム": "Midazolam",
    "ロクロニウム臭化物": "Rocuronium Bromide",
    "ドパミン塩酸塩": "Dopamine Hydrochloride",
    "セファゾリンナトリウム": "Cefazolin Sodium",
    "アセトアミノフェン": "Acetaminophen",
    # ... 依此類推
}

def parse_pdf(file):
    all_data = []
    current_category = "未知類別"
    
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            # 偵測類別標題
            if "(1)" in text or "カテゴリA" in text:
                current_category = "カテゴリ A (最優先)"
            elif "(2)" in text or "カテゴリB" in text:
                current_category = "カテゴリ B (優先)"
            elif "(3)" in text or "カテゴリC" in text:
                current_category = "カテゴリ C (安定確保)"

            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    # 過濾掉空行或標題行
                    if not row or len(row) < 3: continue
                    
                    route = str(row[0]).strip().replace('\n', '')
                    class_no = str(row[1]).strip().replace('\n', '')
                    name_jp = str(row[2]).strip().replace('\n', '')
                    
                    # 只處理有給藥方式符號的列
                    if route in ['内', '注', '外']:
                        name_en = EN_MAPPING.get(name_jp, "Searching...") # 沒對照到的顯示預設值
                        
                        all_data.append({
                            "類別": current_category,
                            "給藥方式": route,
                            "用途分類編號": class_no,
                            "成分日文名": name_jp,
                            "成分英文名": name_en
                        })
    return pd.DataFrame(all_data)

# Streamlit 介面
st.set_page_config(page_title="日本安定確保醫藥品對照工具", layout="wide")
st.title("💊 安定確保醫藥品清單抓取器")
st.write("請上傳日本厚勞省發佈的「安定確保医薬品」PDF 檔案以進行自動解析。")

uploaded_file = st.file_uploader("選擇 PDF 檔案", type="pdf")

if uploaded_file is not None:
    with st.spinner('正在解析 PDF 表格中...'):
        df = parse_pdf(uploaded_file)
        
    if not df.empty:
        st.success(f"成功抓取 {len(df)} 項成分！")
        
        # 篩選器
        cats = st.multiselect("篩選類別", options=df["類別"].unique(), default=df["類別"].unique())
        routes = st.multiselect("篩選給藥方式", options=df["給藥方式"].unique(), default=df["給藥方式"].unique())
        
        filtered_df = df[(df["類別"].isin(cats)) & (df["給藥方式"].isin(routes))]
        
        # 輸出表格
        st.dataframe(filtered_df, use_container_width=True)
        
        # 下載按鈕
        csv = filtered_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("下載解析結果 (CSV)", csv, "medicine_list.csv", "text/csv")
    else:
        st.error("未能識別表格內容，請檢查 PDF 格式。")
