import streamlit as st
import pandas as pd
import io

# --- 核心邏輯：AI 提示詞工程 ---
def generate_prompt(drug_list):
    """
    生成一個專業的指令，讓 AI 幫您完成對照
    """
    prompt = """
    你是一位專業的藥劑師與醫學翻譯專家。請將以下日文藥品成分名轉換為標準的國際非專利藥名 (INN) 或 JAN 英文名。
    要求：
    1. 僅回傳英文成分名，多個成分用 ' / ' 分隔。
    2. 確保化學鹽類（如塩酸塩、硫酸塩）翻譯正確（Hydrochloride, Sulfate 等）。
    3. 格式請保持與輸入順序一致。
    
    待處理清單：
    """
    return prompt + "\n".join(drug_list)

# --- UI 介面 ---
st.set_page_config(layout="wide")
st.title("🤖 AI Mode 醫藥對照助手")
st.markdown("參考您分享的 AI 模式，利用大語言模型的醫藥知識庫直接完成 505 項對照。")

f = st.file_uploader("上傳您的 505 項 CSV", type=['csv'])

if f:
    df = pd.read_csv(f)
    # 預覽數據
    st.write("### 原始數據預覽", df.head(10))
    
    batch_size = 50  # 建議分批處理以確保準確度
    if st.button(f"🚀 生成 AI 處理指令 (每批 {batch_size} 項)"):
        # 我們將 505 項拆分成幾組，方便您貼入 AI (如 Gemini/ChatGPT)
        drug_names = df['成分日文名'].tolist()
        
        for i in range(0, len(drug_names), batch_size):
            batch = drug_names[i:i + batch_size]
            st.write(f"#### 第 {i//batch_size + 1} 批次指令 (第 {i+1} 至 {min(i+batch_size, 505)} 項)")
            st.code(generate_prompt(batch), language="text")
            st.info("請將上方代碼複製並貼入 AI 視窗，完成後將結果貼回下方表格。")

    # 提供一個編輯區讓使用者貼回結果
    st.write("---")
    st.write("### 📥 貼回 AI 處理結果")
    if '成分英文名' not in df.columns:
        df['成分英文名'] = ""
    
    edited_df = st.data_editor(df, use_container_width=True)
    
    if st.button("💾 匯出最終完美版 CSV"):
        csv_data = edited_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下載對照完成檔案", csv_data, "Medicine_AI_Final_Fixed.csv")
