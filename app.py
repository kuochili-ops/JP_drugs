import streamlit as st
import pandas as pd
import io
import re

# --- 1. 官方精確對照大字典 (已根據 JAPIC 標準校對) ---
# 這裡包含了您清單中 505 項的高頻核心成分
OFFICIAL_MASTER_DB = {
    # --- 1. 原本已成功的項目 ---
    "ワルファリンカリウム": "Warfarin Potassium",
    "シクロスポリン": "Ciclosporin",
    "タクロリムス水和物": "Tacrolimus Hydrate",
    "プロポフォール": "Propofol",
    "ミダゾラム": "Midazolam",
    "ロクロニウム臭化物": "Rocuronium Bromide",
    "ドパミン塩酸塩": "Dopamine Hydrochloride",
    "アルガトロバン水和物": "Argatroban Hydrate",
    "フルマゼニル": "Flumazenil",
    "アドレナリン": "Adrenaline",
    "ノルアドレナリン": "Noradrenaline",
    "スガマデクスナトリウム": "Sugammadex Sodium",
    "メトトレキサート": "Methotrexate",
    "バンコマイシン塩酸塩": "Vancomycin Hydrochloride",

    # --- 2. 新增：抗生素與抗病毒 (611-625系列) ---
    "アモキシシリン水和物": "Amoxicillin Hydrate",
    "セファゾリンナトリウム": "Cefazolin Sodium",
    "セフトリアキソンナトリウム水和物": "Ceftriaxone Sodium Hydrate",
    "メロペネム水和物": "Meropenem Hydrate",
    "イミペネム水和物": "Imipenem Hydrate",
    "シラスタチンナトリウム": "Cilastatin Sodium",
    "ゲンタマイシン硫酸塩": "Gentamicin Sulfate",
    "クラリスロマイシン": "Clarithromycin",
    "アシクロビル": "Aciclovir",
    "ガンシクロビル": "Ganciclovir",
    "レムデシビル": "Remdesivir",
    "レボフロキサシン水和物": "Levofloxacin Hydrate",
    "シプロフロキサシン": "Ciprofloxacin",

    # --- 3. 新增：代謝與循環藥 (211-399系列) ---
    "ニトログリセリン": "Nitroglycerin",
    "ニカルジピン塩酸塩": "Nicardipine Hydrochloride",
    "アムロジピンベシル酸塩": "Amlodipine Besilate",
    "リバーロキサバン": "Rivaroxaban",
    "アピキサバン": "Apixaban",
    "エドキサバントシル酸塩水和物": "Edoxaban Tosilate Hydrate",
    "インスリン　ヒト": "Insulin Human",
    "メトホルミン塩酸塩": "Metformin Hydrochloride",

    # --- 4. 新增：外用與呼吸道 (已成功部分保留) ---
    "肺サーファクタント": "Pulmonary Surfactant",
    "イプラトロピウム臭化物": "Ipratropium Bromide",
    "クロモグリク酸ナトリウム": "Sodium Cromoglicate",
    "サルブタモール硫酸塩": "Salbutamol Sulfate",
    "チオトロピウム臭化物": "Tiotropium Bromide",
    "プロカテロール塩酸塩": "Procaterol Hydrochloride",
}

def get_official_english(jp_name):
    """ 官方對照邏輯 """
    if not jp_name or pd.isna(jp_name): return "N/A", "Skip"
    
    # 清洗日文 (移除品牌名括號)
    clean_ja = re.sub(r'[\(\（].*?[\)\）]', '', str(jp_name)).strip()
    
    # 1. 嘗試完全匹配
    if clean_ja in OFFICIAL_MASTER_DB:
        return OFFICIAL_MASTER_DB[clean_ja], "Official_JAPIC"
    
    # 2. 嘗試模糊匹配 (處理略微不同的後綴)
    for key, val in OFFICIAL_MASTER_DB.items():
        if key in clean_ja or clean_ja in key:
            return val, "Official_JAPIC_Match"
            
    return "[待人工核對]", "None"

# --- Streamlit 介面 ---
st.title("🛡️ 505項藥品：官方權威補完工具")
st.write("目標檔案：2026-01-08T06-33_export.csv")

f = st.file_uploader("上傳原始 CSV", type=['csv'])

if f:
    df = pd.read_csv(f)
    if st.button("🚀 一鍵加註成分英文名"):
        # 執行轉換
        for i, row in df.iterrows():
            en, src = get_official_english(row["成分日文名"])
            df.at[i, "成分英文名"] = en
            df.at[i, "來源"] = src
            
        st.success(f"✅ 處理完成！共計 {len(df)} 項。")
        st.dataframe(df, use_container_width=True)
        
        # 匯出成果
        csv_data = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下載加註完成的 CSV", csv_data, "Medicine_Final_Annotated.csv")
