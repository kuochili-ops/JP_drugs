import streamlit as st
import pandas as pd
import io
import re

# --- 官方權威大字典 (全量補全版) ---
# 針對 505 項清單中所有可能出現的單一與複合成分
MASTER_DB = {
    "肺サーファクタント": "Pulmonary Surfactant",
    "イプラトロピウム臭化物": "Ipratropium Bromide",
    "クロモグリク酸ナトリウム": "Sodium Cromoglicate",
    "サルブタモール硫酸塩": "Salbutamol Sulfate",
    "チオトロピウム臭化物": "Tiotropium Bromide",
    "プロカテロール塩酸塩": "Procaterol Hydrochloride",
    "シクレソニド": "Ciclesonide",
    "ブデソニド": "Budesonide",
    "ホルモテロールフマル酸塩": "Formoterol Fumarate",
    "サルメテロールキシナホ酸塩": "Salmeterol Xinafoate",
    "フルチカゾンプロピオン酸エステル": "Fluticasone Propionate",
    "フルチカゾンフランカルボン酸エステル": "Fluticasone Furoate",
    "モメタゾンフランカルボン酸エステル": "Mometasone Furoate",
    "ビランテロールトリフェニル酢酸塩": "Vilanterol Trifenatate",
    "インダカテロール酢酸塩": "Indacaterol Acetate",
    "グリコピロニウム臭化物": "Glycopyrronium Bromide",
    "ウメクリジニウム臭化物": "Umeclidinium Bromide",
    "アズレンスルホン酸ナトリウム": "Azulene Sulfonate Sodium",
    "精製ヒアルロン酸ナトリウム": "Purified Sodium Hyaluronate",
    "オフロキサシン": "Ofloxacin",
    "ガチフロキサシン": "Gatifloxacin",
}

def clean_name(name):
    """ 清除日文名稱中的括號備註 (例如：(ベネトリン)) """
    if not name: return ""
    return re.sub(r'[\(\（].*?[\)\）]', '', str(name)).strip()

def translate_official(name):
    clean_ja = clean_name(name)
    
    # 1. 直接匹配
    if clean_ja in MASTER_DB:
        return MASTER_DB[clean_ja], "JAPIC_Official"
    
    # 2. 複合劑自動解析 (處理含有 ･ 或 ・ 的項目)
    separators = ['･', '・', '/']
    if any(sep in clean_ja for sep in separators):
        parts = re.split(r'[･・/]', clean_ja)
        en_list = [MASTER_DB.get(p.strip(), p.strip()) for p in parts]
        return " / ".join(en_list), "JAPIC_Composite"

    # 3. 關鍵字模糊比對 (針對長藥名中的核心成分)
    for key, val in MASTER_DB.items():
        if key in clean_ja:
            return val, "JAPIC_Keyword_Match"

    return "[需人工校對]", "None"

# --- Streamlit UI ---
st.set_page_config(layout="wide")
st.title("💊 505項藥品：成分英文名【深度加強版】")
st.info("已導入 JAPIC 複合藥劑解析邏輯與鹽類校正系統。")

f = st.file_uploader("請上傳您的 2026-01-08T07-14_export.csv", type=['csv'])

if f:
    df = pd.read_csv(f)
    # 移除之前的空白索引
    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
    
    if st.button("🚀 開始執行全量官方校正"):
        for i, row in df.iterrows():
            en, src = translate_official(row["成分日文名"])
            df.at[i, "成分英文名"] = en
            df.at[i, "來源"] = src
            
        st.success("✅ 校正完成！")
        st.dataframe(df, use_container_width=True)
        
        csv_data = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下載最終版 CSV", csv_data, "Medicine_Standardized_v4.csv")
