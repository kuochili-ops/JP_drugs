import pandas as pd
import requests
import io

def fetch_and_fill_kegg_data(input_df):
    """
    input_df 必須包含 '品項名稱' 欄位
    會補齊 'KEGG_ID' 與 '成分名_英' 欄位
    """
    # 1. 從 KEGG API 下載最新的日本醫藥品對照清單 (dr_ja)
    print("正在從 KEGG 下載最新對照數據...")
    url = "https://rest.kegg.jp/list/dr_ja"
    response = requests.get(url)
    
    if response.status_code != 200:
        print("無法連接至 KEGG API")
        return input_df

    # 2. 解析 KEGG 原始數據 (格式為: ID \t 名稱1; 名稱2; (成分名英))
    kegg_list = []
    for line in response.text.strip().split('\n'):
        parts = line.split('\t')
        if len(parts) < 2:
            continue
        
        kegg_id = parts[0].replace("dr:", "")
        full_name = parts[1]
        
        # 提取括號內的英文名 (通常在最後一個括號)
        eng_name = ""
        if "(" in full_name and ")" in full_name:
            eng_name = full_name[full_name.rfind("(")+1 : full_name.rfind(")")]
        
        # 提取日文名 (拿第一個分號前的內容)
        jap_name = full_name.split(';')[0].split(' (')[0].strip()
        
        kegg_list.append({
            'KEGG_ID': kegg_id,
            '品項名稱': jap_name,
            '成分名_英_NEW': eng_name
        })

    kegg_ref_df = pd.DataFrame(kegg_list)

    # 3. 與原本的資料進行合併 (左合併)
    # 假設 input_df 有一欄叫 '品項名稱'
    result_df = pd.merge(input_df, kegg_ref_df, on='品項名稱', how='left')

    # 4. 補齊空缺值
    result_df['KEGG_ID'] = result_df['KEGG_ID'].fillna(result_df['KEGG_ID_NEW'])
    result_df['成分名 (英)'] = result_df['成分名 (英)'].fillna(result_df['成分名_英_NEW'])

    # 移除暫存欄位
    result_df = result_df.drop(columns=['KEGG_ID_NEW', '成分名_英_NEW'])
    
    return result_df

# --- 使用範例 ---
data = {
    '品項名稱': ['アスピリン', 'アセトアミノフェン', 'ロキソプロフェンナトリウム水和物'],
    'KEGG_ID': [None, None, None],
    '成分名 (英)': [None, None, None]
}
my_df = pd.DataFrame(data)

final_df = fetch_and_fill_kegg_data(my_df)
print(final_df)
