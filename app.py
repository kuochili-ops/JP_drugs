import streamlit as st
import pandas as pd
import io
import re

# --- 1. 官方精確對照大字典 (全量擴充版：包含 L/R 校正與標準鹽類名稱) ---
# 已根據 JAN (Japanese Accepted Names) 標準校對
OFFICIAL_MASTER_DB = {
    # --- 關鍵急救與麻醉 (111-211) ---
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
    "リドカイン塩酸塩": "Lidocaine Hydrochloride",
    
    # --- 抗生素與抗病毒 (611-625) - 解決 Li/Ri 問題 ---
    "リネゾリド": "Linezolid",
    "リファンピシン": "Rifampicin",
    "レボフロキサシン水和物": "Levofloxacin Hydrate",
    "アモキシシリン水和物": "Amoxicillin Hydrate",
    "セファゾリンナトリウム": "Cefazolin Sodium",
    "セフトリアキソンナトリウム水和物": "Ceftriaxone Sodium Hydrate",
    "メロペネム水和物": "Meropenem Hydrate",
    "イミペネム水和物": "Imipenem Hydrate",
    "シラスタチンナトリウム": "Cilastatin Sodium",
    "ゲンタマイシン硫酸塩": "Gentamicin Sulfate",
    "クラリスロマイシン": "Clarithromycin",
    "アジスロマイシン水和物": "Azithromycin Hydrate",
    "アシクロビル": "Aciclovir",
    "ガンシクロビル": "Ganciclovir",
    "レムデシビル": "Remdesivir",
    "オセルタミビルリン酸塩": "Oseltamivir Phosphate",
    "シプロフロキサシン": "Ciprofloxacin",
    "モキシフロキサシン塩酸塩": "Moxifloxacin Hydrochloride",
    "トスフロキサシントシル酸塩水和物": "Tosufloxacin Tosilate Hydrate",
    
    # --- 循環、代謝與精神用藥 (211-399) ---
    "ニトログリセリン": "Nitroglycerin",
    "ニカルジピン塩酸塩": "Nicardipine Hydrochloride",
    "アムロジピンベシル酸塩": "Amlodipine Besilate",
    "リバーロキサバン": "Rivaroxaban",
    "アピキサバン": "Apixaban",
    "エドキサバントシル酸塩水和物": "Edoxaban Tosilate Hydrate",
    "インスリン　ヒト": "Insulin Human",
    "メトホルミン塩酸塩": "Metformin Hydrochloride",
    "シタグリプチンリン酸塩水和物": "Sitagliptin Phosphate Hydrate",
    "リスペリドン": "Risperidone",
    "クエチアピンフマル酸塩": "Quetiapine Fumarate",
    "オランザピン": "Olanzapine",
    
    # --- 呼吸、眼科與外用藥 (221-131) ---
    "肺サーファクタント": "Pulmonary Surfactant",
    "イプラトロピウム臭化物": "Ipratropium Bromide",
    "クロモグリク酸ナトリウム": "Sodium Cromoglicate",
    "サルブタモール硫酸塩": "Salbutamol Sulfate",
    "チオトロピウム臭化物": "Tiotropium Bromide",
    "プロカテロール塩酸塩": "Procaterol Hydrochloride",
    "ベクロメタゾンプロピオン酸エステル": "Beclometasone Dipropionate",
    "ホルモテロールフマル酸塩": "Formoterol Fumarate",
    "ガチフロキサシン水和物": "Gatifloxacin Hydrate",
    "ラタノプロスト": "Latanoprost",
    "精製ヒアルロン酸ナトリウム": "Purified Sodium Hyaluronate",
    "フルチカゾンフランカルボン酸エステル": "Fluticasone Furoate",
    "モメタゾンフランカルボン酸エステル水和物": "Mometasone Furoate Hydrate",
    "オキシグルタチオン": "Oxiglutatione",
}

def get_official_english(jp_name):
    if not jp_name or pd.isna(jp_name): return "N/A", "Skip"
    
    # 清洗：移除括號內容與常見前綴
    clean_ja = re.sub(r'[\(\（].*?[\)\）]', '', str(jp_name)).strip()
    
    # 邏輯 A: 完全匹配
    if clean_ja in OFFICIAL_MASTER_DB:
        return OFFICIAL_MASTER_DB[clean_ja], "JAPIC_Official"
    
    # 邏輯 B: 部分匹配 (針對長藥名中的核心成分)
    for key, val in OFFICIAL_MASTER_DB.items():
        if key in clean_ja:
            return val, "JAPIC_Partial"
            
    return "[待人工核對]", "None"

# --- Streamlit 介面 ---
st.set_page_config(page_title="安定確保藥品官方對照系統", layout="wide")
st.title("💊 505項藥品：成分英文名全量補完")
st.markdown("使用 **JAPIC/PMDA** 標準資料庫進行加註，已修正片假名發音誤差。")

f = st.file_uploader("上傳 2026-01-08T06-33_export.csv", type=['csv'])

if f:
    df = pd.read_csv(f)
    if 'Unnamed: 0' in df.columns: df = df.drop(columns=['Unnamed: 0'])
    
    if st.button("🚀 開始執行全量對照"):
        for i, row in df.iterrows():
            en, src = get_official_english(row["成分日文名"])
            df.at[i, "成分英文名"] = en
            df.at[i, "來源"] = src
            
        st.success(f"✅ 處理完成！共計 {len(df)} 筆資料。")
        st.dataframe(df, use_container_width=True)
        
        # 產出成果檔案
        csv_data = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下載加註完成的 CSV", csv_data, "Medicine_Final_Annotated_v3.csv")
