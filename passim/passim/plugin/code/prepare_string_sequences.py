# coding: utf-8
"""
    Converts series of sermons into sequences of characters
    (Japanese hieroglyphs, kanji)
"""

from utils_preprocessing import get_omeliari_sequences, get_passim_sequences, get_passim_json, get_sermons_distance, get_passim_data_from_db, get_passim_core_from_custom_db
import pandas as pd
import sqlite3
import numpy as np
from sklearn.cluster import KMeans
from scipy.cluster.hierarchy import dendrogram, linkage
from matplotlib import pyplot as plt
from sklearn.feature_extraction.text import TfidfVectorizer
# http://www.rikai.com/library/kanjitables/kanji_codes.unicode.shtml
# Kanji: CJK unifed ideographs - Common and uncommon kanji ( 4e00 - 9faf)
# we use Japanese hieroglyphs to work with sequences as strings
JAP_CHARS = [chr(char_id) for char_id in range(int("4e00", base=16), int("9faf", base=16) + 1)]

# a function that creates a peculiar substitution matrix where matches of frequent sermons to themselves
# still have a penalty.
def get_frequency_weights(series, char_codes, data_location):

    char_codes.set_index("SermonName", inplace=True)
    def get_code(char_codes, x):

        if x not in char_codes.index:
            print(f"Key {x} not found in char_codes dictionary.")
            return None
        elif "Code" not in char_codes.columns:
            print(f"Key 'Code' not found in char_codes[{x}] dictionary.")
            return None
        else:
            return char_codes.loc[x]["Code"]
    # for each sermon that travelled in collection, comma-separated list of collections
    collections_df = pd.read_csv("../data/collections.tsv", sep="\t")

    collections_df["Code"] = collections_df["SermonName"].apply(lambda x: get_code(char_codes=char_codes, x=x))

    # list of popular collections: sermons belonging to these collections will still have penalty when aligned to themselves
    pop_col = [
        "Alanus of Farfa's Homiliary",
        "Paul the Deacon's Homiliary",
        "De verbis domini et apostoli",
        "Sancti Catholici Patres",
        "Quinquaginta",
    ]

    # filter to get the sermons that belong to popular collections
    popular_sermons_filter = collections_df["Collections"].apply(lambda x: True if len(set(pop_col).intersection(set(x.split(",")))) > 0 else False)

    popular_sermon_idx = collections_df.loc[popular_sermons_filter]["Code"].unique().tolist()

    # creating a substitution matrix with amended diagonal
    freq_df = pd.DataFrame(index=char_codes.Code.tolist(), columns=char_codes.Code.tolist())
    freq_df.fillna(-5.0, inplace=True) # base, mismatches;

    for i in freq_df.columns:
        # chaning scores of popular sermons that match themselves
        if i in popular_sermon_idx:
            print(f"""{i} {char_codes[char_codes["Code"] == i].index} is popular""")
            freq_df[i].loc[i] = -2.0 # also, it might be possible to keep this to 0, but agment the raward to rare ones
            continue
        freq_df[i].loc[i] = 0.0
        # gap will be -2

    # here, we also compute idf, although it's not used (as of yet, at least)
    data = {k: ' '.join([c for c in v]) for k, v in series["EncodedWorks"].iteritems()}

    documents = list(data.values())

    vectorizer = TfidfVectorizer(analyzer='char', lowercase=False)

    vectorizer.fit_transform(documents)

    feature_names = vectorizer.get_feature_names_out().tolist()

    idf_values = vectorizer.idf_

    # normalizing idf values to range 0-1
    min_idf, max_idf = np.min(idf_values), np.max(idf_values)
    idf_values = (idf_values - min_idf) / (max_idf - min_idf)

    # dict to store the idf values of each sermon
    idf_dict = {word: idf for word, idf in zip(feature_names, idf_values)}
    idf_dict.pop(" ")
    idf_matrix = pd.DataFrame.from_dict(idf_dict, orient="index", columns=["IDF"])
    idf_matrix.index.name = 'EncodedWork'

    # creating groups based on idf values
    kmeans = KMeans(n_clusters=4, random_state=0)
    kmeans.fit(idf_matrix)
    clusters = kmeans.labels_
    centers = kmeans.cluster_centers_

    idf_matrix["Freq"] = clusters # in this way, we got groups for which the penalty can be diminished differently

    idf_matrix.to_csv(os.path.join(data_location, "..", f"IDF.csv"))
    freq_df.index.name = "text_id"
    freq_df.to_csv(os.path.join(data_location, f"Freq.csv"))
    # freq_df = freq_df.replace(0.0, 3.0)
    # freq_df = freq_df.replace(-1.5, 1.0)
    # freq_df.to_csv(os.path.join(data_location, f"FreqRew.csv"))

    # some quick visual checks
    # print(char_codes[char_codes["Code"] == "丕"].index, freq_df["丕"].sort_values(ascending=True).head(5))
    # print(char_codes[char_codes["Code"] == "买"].index, freq_df["买"].sort_values(ascending=True).head(5))
    # print(char_codes[char_codes["Code"] == "乡"].index, freq_df["乡"].sort_values(ascending=True).head(5))

def kanji_encode( script2works:dict[str, list[str]] ):

    indices, df_data, work2code = [], [], {}

    for script_name in script2works:

        indices.append(script_name)
        char_accumulator = ""

        for work in script2works[script_name]:
            if not work in work2code:
                work2code[work] = JAP_CHARS[len(work2code)]
            char_accumulator = char_accumulator + work2code[work]

        df_data.append(char_accumulator)

    df = pd.DataFrame({"SeriesName": indices, "EncodedWorks": df_data})
    return df, work2code

if __name__ == "__main__":

    import json
    
    import os

    current_dir = os.path.realpath(os.path.dirname(__file__))

    os.makedirs(os.path.join(current_dir, "../preprocessed_data/omeliari"), exist_ok=True)
    os.makedirs(os.path.join(current_dir, "../preprocessed_data/passim_sample"), exist_ok=True) # obsolete, as we added full import directly from the db
    os.makedirs(os.path.join(current_dir, "../preprocessed_data/passim_core"), exist_ok=True)
    os.makedirs(os.path.join(current_dir, "../preprocessed_data/passim_extended"), exist_ok=True)
    os.makedirs(os.path.join(current_dir, "../preprocessed_data/passim_core_custom"), exist_ok=True)


    print("preparing omeliari")
    with open(os.path.join(current_dir, "../data/omeliari_by_ms_7_august_2022.json"), "r+", encoding="utf-8") as rf:
        json_data = json.load(rf)
    script2works = get_omeliari_sequences(json_data)
    df, work2code = kanji_encode( script2works )
    df.to_csv(os.path.join(current_dir,"../preprocessed_data/omeliari/char_series.csv"), index=None)
    work2code_df = pd.DataFrame([{"SermonName": work, "Code": code} for work, code in work2code.items()])
    work2code_df.to_csv(os.path.join(current_dir,"../preprocessed_data/omeliari/char_codes.csv"), index=None)
    os.makedirs(os.path.join(current_dir,"../preprocessed_data/omeliari/char_distances"), exist_ok=True)

    print("preparing passim sample data")
    # old dataset
    passim_dataframe = pd.read_csv(os.path.join(current_dir, "../data/mss_dataset.tsv"), sep="\t")
    script2works = get_passim_sequences(passim_dataframe)
    df, work2code = kanji_encode(script2works)
    df.to_csv(os.path.join(current_dir, "../preprocessed_data/passim_sample/char_series.csv"), index=None)
    work2code_df = pd.DataFrame([{"SermonName": work, "Code": code} for work, code in work2code.items()])
    work2code_df.to_csv(os.path.join(current_dir, "../preprocessed_data/passim_sample/char_codes.csv"), index=None)
    os.makedirs(os.path.join(current_dir, "../preprocessed_data/passim_sample/char_distances"), exist_ok=True)

    print("preparing passim core")
    # new dataset
    with open(os.path.join(current_dir, "../data/sermones_file_dataset_passim_final_.json"), "r+",
              encoding="utf-8") as rf:
        json_data = json.load(rf)

    script2works, metadata = get_passim_json(json_data)
    df, work2code = kanji_encode(script2works)
    df.to_csv(os.path.join(current_dir, "../preprocessed_data/passim_core/char_series.csv"), index=None)
    work2code_df = pd.DataFrame([{"SermonName": work, "Code": code} for work, code in work2code.items()])
    work2code_df.to_csv(os.path.join(current_dir, "../preprocessed_data/passim_core/char_codes.csv"), index=None)

    # get the metadata for coloring and so on
    metadata_df = [
        dict([('SeriesName', name)] + list(metadata[name].items()))
        for name in metadata
    ]
    metadata_df = pd.DataFrame(metadata_df)
    metadata_df.to_csv(os.path.join(current_dir, "../preprocessed_data/passim_core/metadata.csv"), index=None)


    print("preparing passim extended")
    # old dataset
    passim_dataframe = pd.read_csv(os.path.join(current_dir, "../data/mss_dataset.tsv"), sep="\t")
    script2works, metadata = get_passim_data_from_db(sqlite3.connect(os.path.join(current_dir, "../data/passim_13-07-2023.db")))
    df, work2code = kanji_encode( script2works )
    df.to_csv(os.path.join(current_dir,"../preprocessed_data/passim_extended/char_series.csv"), index=None)
    work2code_df = pd.DataFrame([{"SermonName": work, "Code": code} for work, code in work2code.items()])
    work2code_df.to_csv(os.path.join(current_dir,"../preprocessed_data/passim_extended/char_codes.csv"), index=None)
    os.makedirs(os.path.join(current_dir,"../preprocessed_data/passim_extended/char_distances"), exist_ok=True)

    metadata_df = [
        dict( [('SeriesName', name)] + list(metadata[name].items()) )
        for name in metadata
        ]
    metadata_df = pd.DataFrame(metadata_df)
    metadata_df.to_csv(os.path.join(current_dir,"../preprocessed_data/passim_extended/metadata.csv"), index=None)
    
    # sermons distance (LDA)
    LDA = pd.read_csv(os.path.join(current_dir,"../data/sermon_topics_from_weighted_paragraphs.tsv"), sep="\t")
    LDA.set_index("text_id", inplace=True)
    LDA = LDA.drop(columns=["passim", "kw", "hc", "mss", "feast", "feast_category", "popularity", "maurini"])
    mapping = pd.read_csv(os.path.join(current_dir,"../data/sermones_dataset_lda_embeddings_mapping.tsv"), sep ="\t").set_index("ms_dataset_id")

    mapping = mapping["embeddings_id"].to_dict()
    mapping = {mapping[key]:work2code[key]  for key in work2code if key in mapping}

    LDA=LDA[LDA.index.isin(list(mapping.keys()))]
    distance_matrix = get_sermons_distance(LDA, work2code=mapping, dist = "cosine")
    os.makedirs(os.path.join(current_dir,"../preprocessed_data/passim_core/char_distances"), exist_ok=True)
    distance_matrix.to_csv(os.path.join(current_dir,"../preprocessed_data/passim_core/char_distances/LDA_cosine.csv"))


    distance_matrix = get_sermons_distance(LDA, work2code=mapping, dist = "euclidean")
    distance_matrix.to_csv(os.path.join(current_dir,"../preprocessed_data/passim_core/char_distances/LDA_euclidean.csv"))

    print("preparing passim_core_custom")
    # old dataset
    script2works, metadata = get_passim_core_from_custom_db(
        sqlite3.connect(os.path.join(current_dir, "../data/passim_core.db")))
    df, work2code = kanji_encode(script2works)
    df.to_csv(os.path.join(current_dir, "../preprocessed_data/passim_core_custom/char_series.csv"), index=None)
    work2code_df = pd.DataFrame([{"SermonName": work, "Code": code} for work, code in work2code.items()])
    work2code_df.to_csv(os.path.join(current_dir, "../preprocessed_data/passim_core_custom/char_codes.csv"), index=None)
    os.makedirs(os.path.join(current_dir, "../preprocessed_data/passim_core_custom/char_distances"), exist_ok=True)

    metadata_df = [
        dict([('SeriesName', name)] + list(metadata[name].items()))
        for name in metadata
    ]
    metadata_df = pd.DataFrame(metadata_df)
    metadata_df.to_csv(os.path.join(current_dir, "../preprocessed_data/passim_core_custom/metadata.csv"), index=None)

    # sermons distance (LDA)
    LDA = pd.read_csv(os.path.join(current_dir, "../data/sermon_topics_from_weighted_paragraphs.tsv"), sep="\t")
    LDA.set_index("text_id", inplace=True)
    LDA = LDA.drop(columns=["passim", "kw", "hc", "mss", "feast", "feast_category", "popularity", "maurini"])
    mapping = pd.read_csv(os.path.join(current_dir, "../data/passim_core_db_mapping.tsv"),
                          sep="\t").set_index("ms_dataset_id")

    mapping = mapping["embeddings_id"].to_dict()
    mapping = {mapping[key]: work2code[key] for key in work2code if key in mapping}

    LDA = LDA[LDA.index.isin(list(mapping.keys()))]
    distance_matrix = get_sermons_distance(LDA, work2code=mapping, dist="cosine")
    os.makedirs(os.path.join(current_dir, "../preprocessed_data/passim_core_custom/char_distances"), exist_ok=True)
    distance_matrix.to_csv(os.path.join(current_dir, "../preprocessed_data/passim_core_custom/char_distances/LDA_cosine.csv"))

    distance_matrix = get_sermons_distance(LDA, work2code=mapping, dist="euclidean")
    distance_matrix.to_csv(
        os.path.join(current_dir, "../preprocessed_data/passim_core_custom/char_distances/LDA_euclidean.csv"))

    get_frequency_weights(df, work2code_df, "../preprocessed_data/passim_core_custom/char_distances")

 
