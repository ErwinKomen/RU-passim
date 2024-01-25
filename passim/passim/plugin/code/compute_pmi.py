
from collections import defaultdict
import pandas as pd
import re
from tqdm import tqdm
import os

from sklearn.feature_extraction.text import TfidfVectorizer

import logging
import argparse

import numpy as np

from collections import defaultdict

from collections import Counter
import math

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)

def main(metric, outdir, stops, seqs, elements=None, decoder=None, decode=False):
    colloc = CollocationCounter(stops=stops, seqs=seqs, elements=elements, decoder=decoder, decode=decode)

    nodes_fname = os.path.join(outdir, "nodes.tsv")
    nodes = open(nodes_fname, "w")
    nodes.close()

    logging.info(f"Writing nodes...")

    with open(nodes_fname, "a") as nodes:
        nodes.write(f"Id\tLabel\tDecoded\tFreq\n")
        for k, v in sorted(colloc.element_dict.items(), key=lambda x: colloc.element2idx[x[0]], reverse=False):
            nodes.write(f"{colloc.element_dict[k]}\t{k}\t{decoder[decoder['Code'] == k].index[0]}\t{v}\n")

    logging.info(f"Nodes written: {len(colloc.element_dict)} tokens.")

    outfilename = "{}_collocations.tsv"

    if metric == 'series':
        colloc.series_cooccurrences(decode=decode).to_csv(os.path.join(outdir, outfilename.format(metric)), sep="\t")
    elif metric == 'window':
        colloc.window_cooccurences(decode=decode).to_csv(os.path.join(outdir, outfilename.format(metric)), sep="\t")

    elif metric == "pmi":
        colloc.window_pmi(decode=decode).to_csv(os.path.join(outdir, outfilename.format('window_pmi')), sep="\t")
        colloc.series_pmi(decode=decode).to_csv(os.path.join(outdir, outfilename.format('series_pmi')), sep="\t")
    elif metric == "all":
        colloc.series_cooccurrences(decode=decode).to_csv(os.path.join(outdir, outfilename.format('series')), sep="\t")
        colloc.window_cooccurences(decode=decode).to_csv(os.path.join(outdir, outfilename.format('window')), sep="\t")
        colloc.series_pmi(decode=decode).to_csv(os.path.join(outdir, outfilename.format('series_pmi')), sep="\t")
        colloc.window_pmi(decode=decode).to_csv(os.path.join(outdir, outfilename.format('window_pmi')), sep="\t")
    else:
        print("Invalid method. Use 'series', 'window', 'pmi', or 'all'.")



class CollocationCounter:

    def __init__(
            self,
            seqs,
            stops = None,
            elements = None,
            min_fq = 5,
            decoder = None,
            decode = False,
    ):
        """
        A class to compute collocations of words either in sentences, or in windows, or in any provided texts.
        :param element_dict:
        :param seqs:
        :param stops:
        :param min_fq:
        """
        self.min_fq = min_fq
        self.stops = stops if stops and isinstance(stops, list) else []
        self.seqs = seqs
        self.element_dict = self.build_element_dict(element_dict=elements)
        self._window_size = 5
        self._decoder = decoder
        self.decode = decode

        # different edge-weight measures

        self.pmi_window = None
        self.pmi_series = None

        # tf_idf of all the words
        self.tf_idf_dict = {}

        # Index for each word
        self.element2idx = {word: idx for idx, word in enumerate(list(self.element_dict.keys()))}
        self.idx2element = {idx: word for word, idx in self.element2idx.items()}

    def tokenize(self, seq):
        # logging.info(f"Tokenizing...")
        # whitespace tokenizer
        return [el.lower() for el in seq if el not in self.stops and len(el.strip()) != 0]

    def build_element_dict(self, element_dict):
        logging.info(f"Building vocabulary...")
        vocabulary = defaultdict(int)
        for seq in self.seqs:
            for el in seq:
                if element_dict:
                    if el in element_dict:
                        vocabulary[el] += 1
                else:
                    vocabulary[el] += 1

        logging.info(f"There are {len(vocabulary)} unique elements in the sequences.")
        return vocabulary

    def _get_chunks(self, chunk_type=0):
        """
        :param chunk_type:
        :return:

        >>> texts = ["honorius anima talis", "honorius anima anima honorius", "honorius honorius scutum pugna"]
        >>> colloc = CooccurrenceCounter(texts=texts)
        >>> processed_texts = colloc._get_chunks(chunk_type=2)
        >>> assert texts == processed_texts
        >>> texts = ["honorius anima talis. anima non nihil.", "honorius anima. anima honorius.", "honorius honorius. scutum pugna."]
        >>> colloc = CooccurrenceCounter(texts=texts)
        >>> sentences = colloc._get_chunks(chunk_type=0)
        >>> assert sentences == ["honorius anima talis", "anima non nihil", "honorius anima", "anima honorius", "honorius honorius", "scutum pugna"]
        >>> windows = colloc._get_chunks(chunk_type=1)
        """
        if chunk_type == 0: # raw series
            return self.seqs
        elif chunk_type == 1: # windows window - self - window
            windows = []
            for seq in self.seqs:
                tokens = list(seq)
                for i, token in enumerate(tokens):
                    window_chunk = " ".join(tokens[max(0, i - self._window_size):min(i + self._window_size + 1, len(tokens))])
                    windows.append(window_chunk)
            return windows

    def _compute_pair_freqs(self, chunks, count_type=0):
        """
        >>> vocab = {"honorius": 2, "anima": 3, "scutum": 1, "talis": 7}
        >>> texts = ["honorius anima talis", "honorius anima anima honorius", "honorius honorius scutum pugna"]
        >>> colloc = CooccurrenceCounter(vocab=vocab, texts=texts)
        >>> colloc.word2idx = {"honorius": 0, "anima": 1, "scutum": 2, "talis": 3}
        >>> pair_freqs = colloc._compute_pair_freqs(chunks=texts)
        >>> pair_freqs_full = colloc._compute_pair_freqs(chunks=texts, count_type=1)
        >>> assert pair_freqs.astype(int).tolist() == [[0, 2, 1, 1],[0, 0, 0, 1],[0, 0, 0, 0],[0, 0, 0, 0]]
        >>> assert pair_freqs_full.astype(int).tolist() == [[0, 5, 2, 1],[0, 0, 0, 1],[0, 0, 0, 0],[0, 0, 0, 0]]
        """

        pair_freqs = np.zeros((len(self.element_dict), len(self.element_dict)))

        # todo: amend pair freq computation

        for j, chunk in tqdm(enumerate(chunks), total=len(chunks)):
            processed = set()
            words = self.tokenize(chunk)

            for i, word1 in enumerate(words):
                if word1 not in self.element_dict: continue

                for j, word2 in enumerate(words):
                    if word2 not in self.element_dict: continue
                    if i == j or word1 == word2: continue

                    if count_type == 0:
                        if (word1, word2) in processed or (word2, word1) in processed:
                            continue
                    # This code is perhaps unnecessary as we need a symmetric matrix, obviously
                    #elif count_type == 1:
                    #    if (word2, word1) in processed:
                    #        continue

                    pair_freqs[self.element2idx[word1], self.element2idx[word2]] += 1
                    processed.add((word1, word2))

                    if count_type == 0:
                        processed.add((word2, word1))


        self._to_df(matrix=pair_freqs, index=True, decode=True).to_csv("pair_freqs.tsv", sep="\t")


        return pair_freqs

    def _to_df(self, matrix, index=True, decode=None):
        if index:
            idx = [self.idx2element[i] for i in range(matrix.shape[0])]
            cols = [self.idx2element[i] for i in range(matrix.shape[1])]
            # print(idx, cols)
            if decode == True and self._decoder is not None:
                idx = [self._decoder[self._decoder["Code"] == char].index[0] for char in idx]
                cols = [self._decoder[self._decoder["Code"] == char].index[0] for char in cols]

            return pd.DataFrame(
                                matrix,
                                index=idx,
                                columns=cols
                                )
        else:
            return pd.DataFrame(
                                matrix
                                )

    def window_cooccurences(self, count_type=1, index=True, decode=True):
        chunks = self._get_chunks(chunk_type=1)
        logging.info(f"Computing raw pair frequencies for windows...")
        self.window_adj = self._compute_pair_freqs(chunks=chunks, count_type=count_type,)

        return self._to_df(self.window_adj, index=index, decode=decode)

    def series_cooccurrences(self, count_type=0, index=True, decode=True):
        chunks = self._get_chunks(chunk_type=0)
        logging.info(f"Computing raw pair frequencies for series...")
        self.sent_adj = self._compute_pair_freqs(chunks=chunks, count_type=count_type)
        return self._to_df(self.sent_adj, index=index, decode=decode)

    def _compute_pmi(self, k=1.5, normalize=True):

        pair_freqs = np.zeros((len(self.element_dict), len(self.element_dict)))

        for seq in self.seqs:
            tokens = list(seq)
            for i, token in enumerate(tokens):
                word1 = token
                window_chunk = tokens[max(0, i - self._window_size):min(i + self._window_size + 1, len(tokens))]
                for word2 in window_chunk:
                    if word1 == word2: continue
                    pair_freqs[self.element2idx[word1], self.element2idx[word2]] += 1

        for i in range(pair_freqs.shape[0]):
            for j in range(pair_freqs.shape[0]):
                if i == j:
                    pair_freqs[i, j] = self.element_dict[self.idx2element[i]]

        print(pair_freqs)

        self._to_df(matrix=pair_freqs, index=True, decode=True).to_csv("pair_freqs.tsv", sep="\t")

        #total_cooccurrences = np.sum(pair_freqs)
        frequencies = [v for k, v in self.element_dict.items()]
        total_cooccurrences = np.sum(frequencies)
        print(frequencies)
        print(total_cooccurrences)

        pd.DataFrame(frequencies, index=[self._decoder[self._decoder["Code"] == self.idx2element[i]].index[0] for i in range(len(frequencies))]).to_csv("freqs.tsv", sep="\t")

        joint_probabilities = pair_freqs / total_cooccurrences

        # Compute marginal probabilities
        marginal_probabilities = frequencies / total_cooccurrences

        # Initialize PPMI matrix
        ppmi_values = np.zeros_like(pair_freqs, dtype=float)

        # Calculate PPMI values
        for i in range(ppmi_values.shape[0]):
            for j in range(ppmi_values.shape[1]):
                # Calculate the expected probability assuming x and y are independent
                expected_prob = marginal_probabilities[i] * marginal_probabilities[j]

                # Raising joint probability to the power k
                adjusted_joint_prob = joint_probabilities[i, j] ** k

                # If the expected_prob is 0 or adjusted_joint_prob is 0, the PPMI value is 0.
                # Using max to ensure non-negative values.
                ppmi_values[i, j] = max(np.log2((adjusted_joint_prob / expected_prob) + 1e-10), 0)

        if normalize:
            row_min = np.min(ppmi_values, axis=1)[:, np.newaxis]  # Minimum value per row
            row_max = np.max(ppmi_values, axis=1)[:, np.newaxis]  # Maximum value per row
            normalized_matrix = (ppmi_values - row_min) / (row_max - row_min + 1e-10)

            # min_val = np.min(ppmi_values)
            # max_val = np.max(ppmi_values)
            # normalized_matrix = (ppmi_values - min_val) / (max_val - min_val)
            return normalized_matrix

        return ppmi_values

    # def _compute_pmi(self, k=3, chunk_type=0, count_type=1, normalize=True):
    #     chunks = self._get_chunks(chunk_type=chunk_type)
    #
    #     freqs = {}
    #
    #     for c in chunks:
    #        for e in self.tokenize(c):
    #             freqs[e] = freqs.get(e, 0) + 1
    #
    #     pair_freqs = self._compute_pair_freqs(chunks=chunks, count_type=count_type)
    #     # N = len(self.element_dict)
    #     N = np.sum(pair_freqs)
    #     pmi_matrix = np.zeros((len(self.element_dict), len(self.element_dict)))
    #
    #     for x in self.idx2element:
    #         for y in self.idx2element:
    #             if pair_freqs[x][y] == 0: continue
    #             #p_x = freqs[self.idx2element[x]] / N
    #             #p_y = freqs[self.idx2element[y]] / N
    #             p_x = self.element_dict[self.idx2element[x]] / N
    #             p_y = self.element_dict[self.idx2element[y]] / N
    #             p_x_y = pair_freqs[x][y] / N
    #             pmi = math.log2((p_x_y ** k) / (p_x * p_y))
    #             #pmi_matrix[x][y] = max(pmi, 0)
    #             pmi_matrix[x][y] = pmi
    #
    #     if normalize:
    #         min_val = np.min(pmi_matrix)
    #         max_val = np.max(pmi_matrix)
    #         normalized_matrix = (pmi_matrix - min_val) / (max_val - min_val)
    #         return normalized_matrix
    #
    #     else:
    #         return pmi_matrix

    def window_pmi(self, index=True, decode=True):
        logging.info(f"Computing pair frequencies for window PMI...")
        #self.pmi_window = self._compute_pmi(chunk_type=1)
        self.pmi_window = self._compute_pmi()

        return self._to_df(self.pmi_window, index=index, decode=decode)

    def series_pmi(self, index=True, decode=True):
        logging.info(f"Computing pair frequencies for sentence PMI...")
        # self.pmi_sentence =  self._compute_pmi(chunk_type=0)
        self.pmi_sentence =  self._compute_pmi()
        return self._to_df(self.pmi_sentence, index=index, decode=decode)


if __name__ == "__main__":
    current_dir = os.path.realpath(os.path.dirname(__file__))
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset', type=str, help='''
                Dataset to operate on. A folder name in ../preprocessed_data \n
                - "passim_sample" for passim dataset with ~80 sermons,\n
                - "passim_core" for passim dataset with ~750 sermons,\n
                - "passim_core_custom" for passim_core cleaned and put into a db,\n
                - "passim_extended" for a full passim dataset,\n
                - "omeliari" for omeliari
                ''', default='passim_core')
    parser.add_argument("--metric", help="""Metric to compute for windows or entire series. "
                                         'series': raw collocations within entire series,\n
                                         'window': raw collocations within window,\n
                                          'pmi': Pointwise Mutual Information (PMI) computed for entire series and windows,\n
                                          'all': compute all metrics.""", default='all')
    parser.add_argument('--min_len_trashold', default=1, type=int, help='minimal sereies length')
    parser.add_argument('--min_fq', default=1, type=int, help='minimal element corpus frequency')
    parser.add_argument("--source", default="../preprocessed_data")
    parser.add_argument("--sequences", default="char_series.csv")
    parser.add_argument("--outdir", default="../preprocessed_data")
    parser.add_argument("--decode", default=True)
    args = parser.parse_args()

    dataset = args.dataset
    metric = args.metric
    source = args.source


    # loading data
    data_location = os.path.join(current_dir, f"{source}/{dataset}")

    print(data_location)

    char_series = os.path.join(data_location, "char_series.csv")
    char_codes = os.path.join(data_location, "char_codes.csv")

    save_location = os.path.join(data_location, "collocations")
    try:
        os.makedirs(save_location)
    except FileExistsError:
        pass

    codes = pd.read_csv(char_codes).set_index("SermonName")
    series = pd.read_csv(char_series).set_index("SeriesName")

    main(args.metric, save_location, stops=[], seqs=series["EncodedWorks"].tolist(), decoder=codes, decode=True)





