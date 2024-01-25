"""
    by given precomputed distances between individual series, 
    makes clusterization and saves to plotly plots
    
    :TODO  ms_32, ms_3104 и ms_1404 --- highlight
    :TODO what to do with large ghraphs ?? --- augment the length treshold
    :TODO
"""


from scipy.cluster.hierarchy import *
from scipy.spatial.distance import squareform, pdist
import plotly.figure_factory as ff
from string_distance import *

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from tqdm import tqdm
import os
import argparse
import seaborn as sns

datasets = [ "passim2", "passim", "omeliari" ]
current_dir = os.path.realpath(os.path.dirname(__file__))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('dataset', type=str, help='dataset to operate on')
    parser.add_argument('distance_matrix', type=str, help='distance to operate on')
    parser.add_argument('--method', type=str, default='single', help='clustering method to operate on. One of \'single\', \'complete\',\
     \'average\', \'weighted\', \'centroid\',  \'median\' and \'ward\'')
    args = parser.parse_args()

    dataset  = args.dataset
    distance = args.distance_matrix
    method   = args.method
    data_folder = os.path.join( current_dir, f"../preprocessed_data/{dataset}/distances/" )

    # loading data
    dist_file = os.path.join(data_folder, distance)        
    dist_matrix = pd.read_csv(dist_file).set_index("SeriesName")      
    # print(dist_matrix.head())
         
    save_location = os.path.join( current_dir, f"../output/{dataset}/{distance.split('.')[0]}/" )
    os.makedirs(save_location, exist_ok=True)
    dist_condenced = squareform(dist_matrix, force='to_vector')
    order_of_scripts = list(dist_matrix.index)

            
    
    #computing clusters
    # distace = distance.split('.')[0]
    # linkage_matrix = linkage(dist_condenced, method=method)
    # linkage_location = os.path.join( current_dir, f"../output/{dataset}/linkage/{distance}")
    # os.makedirs(linkage_location, exist_ok=True)
    # pd_linkage = pd.DataFrame(linkage_matrix)
    # linkage_matrix.to_csv(os.path.join(linkage_location, f"{method}.csv"))

    plotting dendrograms
    fig = ff.create_dendrogram(dist_matrix, 
        linkagefun = lambda x:linkage(x, method),
        orientation='left',
        labels = dist_matrix.index)
    fig.update_layout(width=1280, height=800)
    # fig.write_html(os.path.join(save_location, "dendrogram_" + method + ".html"))
    # sns.set(rc={'figure.figsize':(50,50)})
    # fig, ax = plt.subplots(figsize=(25,25))
    # ax = dendrogram(linkage_matrix, 
    #                 orientation='right', 
    #                 labels=order_of_scripts)

    # plt.tick_params(
    #     axis='x',
    #     which='both',
    #     bottom='off',
    #     top='off',
    #     )
    # plt.title(f'{dataset}: clustering with {distance.split(".")[0]} distances(method: {method})')
    # plt.tight_layout()
    # plt.savefig(os.path.join(save_location, "dendrogram_" + method + ".png"), dpi=200)
        
           

         
