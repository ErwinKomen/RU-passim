"""
    by given precomputed distances between individual series, 
    makes clusterization and saves to plotly plots
    
    :TODO add weights to special series which are known to be persistent. Gleb will load the list.


"""
# todo: "persistent" and "influential" series: ../data/emblematic_series.json For now, the texts which are not in
#     LDA output can be ignore (to Gleb: to be adjusted for final publication)

from scipy.cluster.hierarchy import *
from scipy.spatial.distance import squareform, pdist

from passim.plugin.code.string_distance import *

from umap.umap_ import UMAP
import plotly.express as px


import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from tqdm import tqdm
import os, time
import seaborn as sns
import plotly.graph_objects as go
from multiprocess import Pool
import argparse
from numba import set_num_threads
from sklearn.feature_extraction.text import TfidfVectorizer


datasets = [ "passim_core", "passim_extended", "omeliari", "passim_sample", "passim_core_custom"]
current_dir = os.path.realpath(os.path.dirname(__file__))



"""
"""

# doesn't work 
NUM_WORKERS= 7
set_num_threads(NUM_WORKERS)


def plotly_heatmap( distances:pd.DataFrame, title:str = "", save_as:str=None ):
    fig = go.Figure()
    try:
        distances.index = distances.index.to_series().apply( lambda x: int(x.split("_")[1]) )
        distances.sort_index(axis=0, ascending=True, inplace=True)
        distances.index = distances.index.to_series().apply( lambda x: "ms_"+str(x) )

        distances.columns = distances.columns.to_series().apply( lambda x: int(x.split("_")[1]) )
        distances.sort_index(axis=1, ascending=True, inplace=True)
        distances.columns = distances.columns.to_series().apply( lambda x: "ms_"+str(x) )
    except:
        distances.sort_index(axis=0, ascending=True, inplace=True)
        distances.sort_index(axis=1, ascending=True, inplace=True)
    fig.add_trace(go.Heatmap(z=distances,
                                    x=distances.columns,
                                    y=distances.columns,
                    ))
    

    fig.update_layout(
        title=title
    )

    # fig.show()
    if save_as is not None:
        fig.write_html(save_as)


def condenced_dist_pair_generator(df: pd.DataFrame):
    order = df.index.to_list()
    progress = tqdm(total = len(order)* ( len(order) - 1) // 2)
    for i, name in enumerate(order):
        for name2 in order[i+1:]:
            # to_compute = [(series.loc[name].EncodedWorks, series.loc[name2].EncodedWorks) for name2 in order[i+1:] ]
            # print(name, name2)
            yield (series.loc[name].EncodedWorks, series.loc[name2].EncodedWorks)
        progress.update(len(order) - i - 1)


def test_metric(s0, s1):
    print(s0,s1)
    return 1
    
metrics = {'LCS' : lcs_heuristic, 
           'SeqMatcher': seq_matcher_ratio_heuristic, 
           'SeqMatcher(parametrized)' : seq_matcher_ratio_heuristic_parametrized, 
           'test' : test_metric,
           'Birnbaum': birnbaum,
           'Jaro-Winkler': jaro_winkler,
           'Ratcliff-Obershlep': ratcliff_obershelp_alcollsim,
           'Jaccard': jaccard,
           }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('dataset', type=str, help='''
        Dataset to operate on. A folder name in ../preprocessed_data \n
        - "passim_sample" for passim dataset with ~80 sermons,\n
        - "passim_core" for passim dataset with ~750 sermons,\n
        - "passim_core_custom" for passim_core cleaned and put into a db,\n
        - "passim_extended" for a full passim dataset,\n
        - "omeliari" for omeliari
        ''')
    parser.add_argument('metric', type=str, help=
        '''Name of distance. Can br one of following:
        - "Edit" for edit distance (make sense with custom char_distance)
        - "SeqMatcher" for seq_matcher_ratio_heuristic
        - "Birnbaum" for Birnbaum distance
        - "Jaro-Winkler" for Jaro-Winkler distance
        - "Ratcliff-Obershelp" for Ratcliff-Obershelp distance
        - "LCS" for longest_common_substring
        - "Jaccard" for Jaccard (ignoring order)
        - "SeqMatcher(parametrized)" for seq_matcher_ratio_heuristic_pure
        ''')
    parser.add_argument('--char_distance',default="Uniform" ,type=str, help='distance to operate on (filename in preprocessed_data/\{dataset\})/char_distances')
    parser.add_argument('--min_len_trashold',default=1 ,type=int, help='minimal sereies length')

    args = parser.parse_args()

    dataset   = args.dataset
    metric    = args.metric
    char_distance = os.path.join(current_dir, f"../preprocessed_data/{dataset}/char_distances/{args.char_distance}")

    #loading data
    data_location = os.path.join(current_dir, f"../preprocessed_data/{dataset}")
    os.makedirs(os.path.join(data_location, "distances"), exist_ok=True)

    char_series = os.path.join(data_location, "char_series.csv")
    char_codes = os.path.join(data_location,  "char_codes.csv" )
    save_location = os.path.join(current_dir, "../output/{}".format(dataset))
    os.makedirs(os.path.join(save_location, "distance_heatmaps"), exist_ok=True)
    os.makedirs(os.path.join(save_location, "umaps"), exist_ok=True)
    codes  = pd.read_csv(char_codes)
    series = pd.read_csv(char_series).set_index("SeriesName")
    char_dist = None
    similarity=None
    
    if metric == 'Edit':
        # LDA based distances if available
        if args.char_distance not in ("Uniform", "Freq.csv"):
            char_dist = pd.read_csv(char_distance)
            char_dist.set_index("text_id", inplace=True)
            # if we use LDA-based char distance, gap_penalty is less than one.
            # Setting to ca. 0.3 gives almost identical results to Uniform
            all = allign( - char_dist, gap_penalty=-0.65)
            good_chars = set(char_dist.columns.to_list())

        # Frequency-weigthed (kind of) substitution matrix, if available
        elif "Freq" in args.char_distance:
            char_dist = pd.read_csv(char_distance)
            char_dist.set_index("text_id", inplace=True)
            all = allign(char_dist, gap_penalty=-3.0)
            # print(char_dist)
            good_chars = set(char_dist.columns.to_list())

        # common edit distance if not
        else:
            # set of all sermons
            good_chars=set( "".join( 
                series["EncodedWorks"].to_list()
                )
            )
            char_score = pd.DataFrame( index=list(good_chars), columns=list(good_chars))
            char_score.fillna(-2, inplace=True)
            for i in char_score.columns:
                char_score[i].loc[i] = 0
            all=allign(char_score)
        all.__name__ = "Edit"
        metrics['Edit'] = all

    # filtering
    def remove_bad_chars(x):
        return "".join([i for i in x if i in good_chars])


    if metric == "Edit":
        series['EncodedWorks'] = series['EncodedWorks'].apply(remove_bad_chars)

    long_serie = series['EncodedWorks'].apply(lambda x: len(x) > args.min_len_trashold)
    
    series = series[ long_serie ]
    order_of_scripts = list(series.index)
    print(f"After filtering total {series.shape[0]} series")
    
    # computing  pairwise summary lengths (for further normalizatrion)
    series_dist = metrics[metric]

    order = list(series.index)
    condenced = []
    sum_lengths_matrix=None
    try:
        sum_lengths_matrix = pd.read_csv(os.path.join(data_location, f"distances/normalization_coefficients.csv"))
        sum_lengths_matrix = sum_lengths_matrix.set_index("SeriesName")
        assert ( sum_lengths_matrix.index.to_series() ==  series.index.to_series() ).all()
        print('found pre-computed normalization_coefficients')

    except Exception as e:
        print("computing normalization coefficients...")
        # diagonal terms are 0, it will produce NaN's if we divide on them
        lengths = map(lambda pair: len(pair[0]) +  len(pair[1]), condenced_dist_pair_generator(series))
        sum_lengths_matrix = pd.DataFrame(
            squareform(list(lengths)),
            columns = series.index.to_list(),
            index = series.index.to_list()
            )
        for i in sum_lengths_matrix.index.to_list():
            sum_lengths_matrix[i].loc[i] = 1
        sum_lengths_matrix.index.name = "SeriesName"
        sum_lengths_matrix.to_csv(os.path.join(data_location, f"distances/normalization_coefficients.csv"))

    print(f"computing {series_dist.__name__} distance ...")
    timestamp = time.time()

    # parralel but not much faster :C
    
    # if series_dist.__name__ == 'ed':
    #     dist_matrix = series_dist.distance_matrix(series['EncodedWorks'])
    # else:

    distances = map(lambda pair: series_dist(pair[0], pair[1]), 
                condenced_dist_pair_generator(series),
                )
    dist_matrix = pd.DataFrame(
        squareform(list(distances)),
        columns = series.index.to_list(),
        index = series.index.to_list()
        )
    dist_matrix.index.name = "SeriesName"

    char_dist_shortname = args.char_distance.split('.')[0]

    print(f"finished in {(time.time() - timestamp):.2f}s. Saving matrices ...")
    os.makedirs(os.path.join(data_location, f"distances/{char_dist_shortname}/"), exist_ok=True)

    dist_matrix_normalized = dist_matrix / sum_lengths_matrix
    dist_matrix.to_csv(os.path.join(data_location, f"distances/{char_dist_shortname}/{metric}.csv"))
    dist_matrix_normalized.to_csv(os.path.join(data_location, f"distances/{char_dist_shortname}/{metric}_normalized.csv"))

