# coding: utf-8

import json

import pandas as pd

from utils_preprocessing import get_omeliari_sequences

if __name__ == "__main__":

    with open("../data/omeliari_by_ms_7_august_2022.json", "r+", encoding="utf-8") as rf:
        json_data = json.load(rf)

    N = 3
    result = get_omeliari_sequences(json_data)
    indices, df_data = [], []

    for script_name in result:
        works_ext = (["START"] * (N - 1)) + result[script_name] + (["END"] * (N - 1))
        ngrams = {"__".join(ngrams): 1 for ngrams in zip(*(works_ext[i:] for i in range(N)))}
        indices.append(script_name)
        df_data.append(ngrams)

    resulting_df = pd.DataFrame(df_data)
    resulting_df["SeriesName"] = indices

    print(resulting_df.shape)
    resulting_df.to_csv(f"../preprocessed_data/bag_of_{N}_sermons.csv", index=False)
