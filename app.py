import streamlit as st
import pandas as pd

df = pd.read_csv('medicine_list.csv')
query = st.text_input("輸入成分英文名或日文名搜尋")
category_filter = st.multiselect("分類過濾", ["Category A", "Category B", "Category C"])

# 過濾與顯示表格
results = df[df['Name_JP'].str.contains(query) | df['Name_EN'].str.contains(query, case=False)]
st.table(results)
