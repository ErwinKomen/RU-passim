# coding: utf-8

import pandas as pd
import numpy as np

import networkx as nx
import matplotlib.pyplot as plt

from utils_strings import longest_common_substring

if __name__ == "__main__":

    THRESHOLD_LCSS = 3

    series2codes = pd.read_csv("../preprocessed_data/char_series.csv")
    sermon2code = {row["Code"]: row["SermonName"] for _, row in pd.read_csv("../preprocessed_data/char_codes.csv").iterrows()}

    lengths = series2codes["EncodedWorks"].map(len)
    series_names = list(series2codes["SeriesName"])
    code_sequences = list(series2codes["EncodedWorks"])

    print("Lenghts:", list(lengths))
    print(f"Mean: {np.mean(lengths):.3f}, Std: {np.std(lengths):.3f}")

    G = nx.Graph()

    for i in range(len(series_names)):

        name0, seq0 = series_names[i], code_sequences[i]

        for j in range(i + 1, len(series_names)):

            name1, seq1 = series_names[j], code_sequences[j]

            if not G.has_node(i):
                G.add_node(i, name=name0, length=lengths[i])

            if not G.has_node(j):
                G.add_node(j, name=name1, length=lengths[j])

            lcsstr, fr, to = longest_common_substring(seq0, seq1)

            if lcsstr > THRESHOLD_LCSS:
                # print("LCSS:", lcsstr)
                G.add_edge(i, j, weight=np.log(lcsstr + 1), weight2=lcsstr)

    # todo: this is more or less HOPELESS, should draw in Gephi for nicer layout
    layout = nx.fruchterman_reingold_layout(G, k=0.6, dim=2, weight="weight", iterations=33)
    labels_edges = nx.get_edge_attributes(G, 'label')
    labels_nodes = nx.get_node_attributes(G, 'name')
    nx.draw_networkx_edge_labels(G, pos=layout, edge_labels=labels_edges)
    nx.draw_networkx(G, layout, with_labels=True, labels=labels_nodes, font_size=6, style="--", alpha=0.9, node_size=150)
    plt.savefig("../output/common-substring-weighted-graph.png")

    nx.write_gexf(G, "../output/longest_common_consecutive_sermons_sequence.gexf")
