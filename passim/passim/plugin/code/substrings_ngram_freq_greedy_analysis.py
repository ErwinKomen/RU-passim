# coding: utf-8
from collections import Counter

import pandas as pd


if __name__ == "__main__":

    script2codes = pd.read_csv("../preprocessed_data/char_series.csv")
    sermon2code = {row["Code"]: row["SermonName"] for _, row in
                   pd.read_csv("../preprocessed_data/char_codes.csv").iterrows()}

    lengths = script2codes["EncodedWorks"].map(len)
    scripts_names = list(script2codes["SeriesName"])
    code_sequences = list(script2codes["EncodedWorks"])

    max_match = 16
    encoded_works = script2codes["EncodedWorks"]

    print("Greedily removing Ngrams of frequency > 1\n")

    for N in range(16, 0, -1):

        print("Frequent N-grams of size", N, ":", end=" ")

        all_N_grams = [string[i:i + N] for string in encoded_works for i in range(0, len(string) - N)]
        counter_tool = Counter(all_N_grams)
        best_k = counter_tool.most_common(len(all_N_grams))
        ngrams_for_removal = []

        for ngram, counter in best_k:
            if counter > 1 and not "*" in ngram:
                # print(" ", ngram, counter)
                ngrams_for_removal.append(ngram)

        print(len(ngrams_for_removal), ":", [(nn, counter_tool.get(nn)) for nn in ngrams_for_removal])

        for ngram in ngrams_for_removal:
            encoded_works = [w.replace(ngram, "*") for w in encoded_works]
