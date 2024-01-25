# coding: utf-8

import pandas as pd
from visedit import StringEdit

from utils_strings import longest_common_substring

if __name__ == "__main__":

    script2codes = pd.read_csv("../preprocessed_data/passim_char_series.csv")
    sermon2code = {row["Code"]: row["SermonName"] for _, row in
                   pd.read_csv("../preprocessed_data/passim_char_codes.csv").iterrows()}

    lengths = script2codes["EncodedWorks"].map(len)
    scripts_names = list(script2codes["SeriesName"])
    code_sequences = list(script2codes["EncodedWorks"])

    for i in range(len(scripts_names)):
        seq0 = code_sequences[i]

        for j in range(i + 1, len(scripts_names)):
            seq1 = code_sequences[j]
            print(f"`{scripts_names[i]}` (len={len(seq0)}) vs `{scripts_names[j]}` (len={len(seq1)})", end=" ")

            sseq0, sseq1 = seq0, seq1
            l, pos0, pos1 = longest_common_substring(sseq0, sseq1)

            if l > 0:
                # todo: visedit isn't perfect (misses important matches!), do NOT rely on its results
                print("\n")
                se = StringEdit(seq0, seq1)
                text = se.generate_text()
                print("  > " + text.replace("\n", "\n  > "))
                print()
            else:
                print("-- nothing in common!")
                continue

            print("")

            while l > 0:
                # print(l, sseq0[pos0:pos0 + l], sseq1[pos1:pos1 + l])
                print(l, [pos0, pos0 + l], [pos1, pos1 + l], end=",   ")
                sseq0 = sseq0.replace(sseq0[pos0:pos0 + l], "*")
                sseq1 = sseq1.replace(sseq1[pos1:pos1 + l], "#")
                l, pos0, pos1 = longest_common_substring(sseq0, sseq1)
            print()
