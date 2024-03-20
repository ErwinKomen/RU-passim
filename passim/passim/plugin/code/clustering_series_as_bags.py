# coding: utf-8

import matplotlib.pyplot as plt
import pandas as pd
from scipy.cluster.hierarchy import *
from sklearn.metrics.pairwise import cosine_similarity


if __name__ == "__main__":

    bag_file = "../preprocessed_data/bag_of_3_sermons.csv"
    df = pd.read_csv(bag_file)
    order_of_scripts = list(df["SeriesName"])
    df.drop("SeriesName", axis=1, inplace=True)

    order_of_originals = df.columns
    X = df.fillna(0).values

    dist_matrix = 1.0 - cosine_similarity(X)
    linkage_matrix = ward(dist_matrix)
    fig, ax = plt.subplots(figsize=(16, 10))

    ax = dendrogram(linkage_matrix, orientation='right', labels=order_of_scripts)

    plt.tick_params(
        axis='x',
        which='both',
        bottom='off',
        top='off',
        labelbottom='off')

    plt.tight_layout()
    plt.savefig(f"../output/clustered-scripts-as-bags_{bag_file.split('/')[-1]}.png")
