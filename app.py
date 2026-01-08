import streamlit as st
import pandas as pd
import requests
import re
from urllib.parse import quote

# 核心：片假名轉英文拼音基礎表 (解決大部分轉換問題)
KATA_TO_EN = {
    'ア': 'a', 'イ': 'i', 'ウ': 'u', 'エ': 'e', 'オ': 'o',
    'カ': 'ka', 'キ': 'ki', 'ク': 'ku', 'ケ': 'ke', 'コ': 'ko',
    'サ': 'sa', 'シ': 'shi', 'ス': 'su', 'セ': 'se', 'ソ': 'so',
    'タ': 'ta', 'チ': 'chi', 'ツ': 'tsu', 'テ': 'te', 'ト': 'to',
    'ナ': 'na', 'ニ': 'ni', 'ヌ': 'nu', 'ネ': 'ne', 'ノ': 'no',
    'ハ': 'ha', 'ヒ': 'hi', 'フ': 'fu', 'ヘ': 'he', 'ホ': 'ho',
    'マ': 'ma', 'ミ': 'mi', 'ム': 'mu', 'メ': 'me', 'モ': 'mo',
    'ヤ': 'ya', 'ユ': 'yu', 'ヨ': 'yo',
    'ラ': 'ra', 'リ': 'ri', 'ル': 'ru', 'レ': 're', 'ロ': 'ro',
    'ワ': 'wa', 'ン': 'n', 'ガ': 'ga', 'ギ': 'gi', 'グ': 'gu', 'ゲ': 'ge', 'ゴ': 'go',
    'ザ': 'za', 'ジ': 'ji', 'ズ': 'zu', 'ゼ': 'ze', 'ゾ': 'zo',
    'ダ': 'da', 'ヂ': 'ji', 'ヅ': 'zu', 'デ': 'de', 'ド': 'do',
    'バ': 'ba', 'ビ': 'bi', 'ブ': 'bu', 'ベ': 'be', 'ボ': 'bo',
    'パ': 'pa', 'ピ': 'pi', 'プ': 'pu', 'ペ': 'pe', 'ポ': 'po',
    'ャ': 'ya', 'ュ': 'yu', 'ョ': 'yo', 'ッ': '', 'ー': ''
}

# 鹽類與後綴對應
SUFFIX_CLEAN = {
    "塩酸塩": " hydrochloride", "硫酸塩": " sulfate", "カリウム": " potassium",
    "ナトリウム": " sodium", "水和物": " hydrate", "フマル酸塩": " fumarate"
}

def auto_translate(text):
    """ 引擎1：邏輯翻譯 (不依賴詞庫) """
    if not text: return ""
    # 移除括號雜訊
    text = re.sub(r'[\(\（].*?[\)\）]', '', str(text)).strip()
    
    # 處理鹽類後綴分離
    suffix_en = ""
    for ja, en in SUFFIX_CLEAN.items():
        if ja in text:
            suffix_en = en
            text = text.replace(ja, "")
            break
            
    # 執行音譯轉換
    res = "".join([KATA_TO_EN.get(char, char) for char in text])
    return res.capitalize() + suffix_en

def get_pubchem_standard(eng_name):
    """ 引擎2：外部資源校正 (向 PubChem 驗證) """
    try:
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{quote(eng_name)}/synonyms/JSON"
        resp = requests.get(url, timeout=3)
        if resp.status_code == 200:
            return resp.json()['InformationList']['Information'][0]['Synonym'][0]
    except:
        pass
    return eng_name # 查不到就用翻譯好的

def process_line(ja_name):
    # 處理複合劑
    if '･' in ja_name or '・' in ja_name:
        parts = re.split(r'[･・]', ja_name)
        return " / ".join([get_pubchem_standard(auto_translate(p)) for p in parts])
    return get_pubchem_standard(auto_translate(ja_name))

# --- UI ---
st.title("🌐 外部資源 + 邏輯翻譯器 (505項全自動版)")
st.write("此版本優先使用邏輯音譯，再由外部數據庫 PubChem 進行名稱校正。")

f = st.file_uploader("上傳最後一份 CSV", type=['csv'])

if f:
    df = pd.read_csv(f)
    if st.button("🚀 啟動 505 項掃描 (不需詞庫)"):
        with st.spinner('引擎啟動中...'):
            df['成分英文名'] = df['成分日文名'].apply(process_line)
            df['來源'] = "Auto_Logic_PubChem"
        st.success("✅ 處理完成！")
        st.dataframe(df)
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下載全自動對應 CSV", csv, "Medicine_Auto_Final.csv")
