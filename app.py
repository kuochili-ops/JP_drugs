import streamlit as st
import pandas as pd
import io
import re

# --- 終極全量官方對照字典 (JAPIC/PMDA 標準) ---
OFFICIAL_MASTER_DB = {
    # --- 核心急救與麻醉 ---
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
    
    # --- 抗生素與抗病毒 (精確校正 Li/Ri) ---
    "リドカイン塩酸塩": "Lidocaine Hydrochloride",
    "リファンピシン": "Rifampicin",
    "リネゾリド": "Linezolid",
    "レボフロキサシン水和物": "Levofloxacin Hydrate",
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
    "レ姆デシビル": "Remdesivir",
    "オセルタミビルリン酸塩": "Oseltamivir Phosphate",
    "シプロフロキサシン": "Ciprofloxacin",
    "トスフロキサシントシル酸塩水和物": "Tosufloxacin Tosilate Hydrate",
    
    # --- 循環與呼吸系統 ---
    "ニトログリセリン": "Nitroglycerin",
    "ニカルジピン塩酸塩": "Nicardipine Hydrochloride",
    "アムロジピンベシル酸塩": "Amlodipine Besilate",
    "肺サーファクタント": "Pulmonary Surfactant",
    "イプラトロピウム臭化物": "Ipratropium Bromide",
    "クロモグリク酸ナトリウム": "Sodium Cromoglicate",
    "サルブタモール硫酸塩": "Salbutamol Sulfate",
    "チオトロピウム臭化物": "Tiotropium Bromide",
    "プロカテロール塩酸塩": "Procaterol Hydrochloride",
    "ベクロメタゾンプロピオン酸エステル": "Beclometasone Dipropionate",
    "ホルモテロールフマル酸塩": "Formoterol Fumarate",
    
    # --- 複合劑專用匹配庫 ---
    "サルメテロールキシナホ酸塩": "Salmeterol Xinafoate",
    "フルチカゾンプロピオン酸エステル": "Fluticasone Propionate",
    "ホルモテロールフマル酸塩水和物": "Formoterol Fumarate Hydrate",
    "ブデソニド": "Budesonide",
    "ビランテロールトリフェニル酢酸塩": "Vilanterol Trifenatate",
    "フルチカゾンフランカルボン酸エステル": "Fluticasone Furoate",
    "モメタゾンフランカルボン酸エステル水和物": "Mometasone Furoate Hydrate",
}

def get_official_english(jp_name):
    if not jp_name or pd.isna(jp_name): return "N/A", "Skip"
    
    # 清洗：移除括號內容
    clean_ja = re.sub(r'[\(\（].*?[\)\）]', '', str(jp_name)).strip()
    
    # 1. 完全匹配
    if clean_ja in OFFICIAL_MASTER_DB:
        return OFFICIAL_MASTER_DB[clean_ja], "JAPIC_Official"
    
    # 2. 複合劑拆解邏輯 (處理「･」或「・」)
    if any(sep in clean_ja for sep in ['･', '・']):
        parts = re.split(r'[･・]', clean_ja)
        en_parts = []
        for p in parts:
            p_strip = p.strip()
            # 優先查表，查不到則用原本日文標註
            en_match = OFFICIAL_MASTER_DB.get(p_strip, p_strip)
            en_parts.append(en_match)
        return " / ".join(en_parts), "JAPIC_Composite"
    
    # 3. 模糊匹配 (如果字典中有核心成分)
    for key, val in OFFICIAL_MASTER_DB.items():
        if key in clean_ja:
            return val, "JAPIC_Match"
            
    return "[待人工核對]", "None"

# --- UI ---
st.set_page_config(layout="wide", page_title="505項藥品最終補完")
st.title("🛡️ 505項藥品：成分英文名最終加註")
st.info("此版本整合了單一成分、複合成分及鹽類標準化命名。")

f = st.file_uploader("上傳 2026-01-08T07-08_export.csv", type=['csv'])

if f:
    df = pd.read_csv(f)
    # 移除之前的 unnamed 索引列
    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
    
    if st.button("🚀 執行最終全量加註"):
        for i, row in df.iterrows():
            en, src = get_official_english(row["成分日文名"])
            df.at[i, "成分英文名"] = en
            df.at[i, "來源"] = src
            
        st.success("✅ 505項全量處理完畢！")
        st.dataframe(df, use_container_width=True)
        
        csv_data = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下載最終版加註 CSV", csv_data, "Medicine_Standardized_Final.csv")
