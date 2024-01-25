#!/bin/pyhon3
import pylcs
from difflib import SequenceMatcher
from enum import IntEnum
import numpy as np
import pandas as pd
from scipy.spatial.distance import squareform
from seqsim.edit import fast_birnbaum_dist, jaro_winkler_dist
from seqsim.sequence import ratcliff_obershelp
from seqsim.token import jaccard_dist

from numba import njit, typed, types, typeof, prange
from numba.experimental import jitclass
from numba_progress import ProgressBar

SIMILARITY_BLOCK_TRASHHOLD = 0

"""
TODO: clean up

"""

# solme anton's heuristics:
def seq_matcher_ratio_heuristic_parametrized(s0, s1, matching_block_min_size=4):
    # todo: i don't like this
    return 2 * sum([block.size for block in SequenceMatcher(a=s0, b=s1).get_matching_blocks()
                    if block.size >= matching_block_min_size])

def seq_matcher_ratio_heuristic(s0, s1):
    return SequenceMatcher(a=s0, b=s1).ratio()

# adding several metrics from seqsim, especially Birnbaum and Jaccard metrics
def birnbaum(s0, s1):
    return fast_birnbaum_dist(s0, s1, normal=False)

def jaro_winkler(s0, s1):
    return jaro_winkler_dist(s0, s1, normal=False)

def ratcliff_obershelp_alcollsim(s0, s1):
    return ratcliff_obershelp(s0, s1, normal=False)

def jaccard(s0, s1):
    return jaccard_dist(s0, s1, normal=False)

def lcs_heuristic(s0, s1):
    return pylcs.lcs(s0, s1)

# FAST allignment 

class allign:

    s2i = types.DictType(types.unicode_type, types.int64)
    spec = [
        ('char_scores', types.float64[:,::1]),          # an array field
        ('SW', types.float64[:,::1]),          # an array field
        ('TB', types.int32[:,::1]),          # an array field
        ('char_to_idx', typeof(typed.Dict.empty(
                key_type=types.unicode_type, 
                value_type=types.int64
                ))),          # an array field
        ('max_score', types.float64),
        ('GA_score', types.float64),
        ('_max_score_index', types.int64),
        # ('STOP':types.int64),
        # ('UP':types.int64),
        # ('LEFT':types.int64),
        # ('DIAG':types.int64)
    ]

    @jitclass(spec)
    class uberfast_allign:

        def __init__(self, char_scores:np.array, char2idx:typed.Dict):
            self.char_scores = char_scores.copy()
            self.char_to_idx = char2idx

            #print(self.char_scores)
            #print(self.char_scores.shape)

            # print(self.char_to_idx)

        def allign(self, s0:str, s1:str, local=False):
            STOP=0
            UP  =1
            LEFT=2
            DIAG=3
   
            # Generating the empty matrices for storing scores and tracing            
            row = len(s0)+1
            col = len(s1)+1

            # Generating the empty matrices for storing scores and tracing
            SW = np.zeros(shape=(row, col), dtype=np.float64) 
            TB = np.zeros(shape=(row, col),dtype=np.int32)

            # Initialising the variables to find the highest scoring cell
            max_score = -1
            max_index = (-1, -1)
            
            # Calculating the scores for all cells in the matrix
            if not local:
                SW[0][0] = 0
                for i in range(1, row):
                    SW[i,0] = i * self.char_scores[ self.char_to_idx[s0[i-1] ], self.char_to_idx['#']]

                for j in range(1, col):
                    SW[0][j] = j * self.char_scores[ self.char_to_idx['#'], self.char_to_idx[s1[j-1]]]

            # print(SW)

            for i in range(1, row):
                for j in range(1, col):
                    scores = np.zeros(4,dtype=np.float64)
                    if not local:
                        scores.fill(-999999.)

                    # Calculating the diagonal score (match score)
                    match_value = self.char_scores[ self.char_to_idx[s0[i-1]], self.char_to_idx[s1[j-1]]]

                    diagonal_score = SW[i - 1, j - 1] + match_value

                    scores[DIAG] = diagonal_score

                    # Calculating the vertical gap score  (aka insert shift to second string score)
                    shift_second_score = SW[i - 1, j] + self.char_scores[ self.char_to_idx[s0[i-1]], self.char_to_idx["#"]]
                    scores[UP] = shift_second_score

                    # Calculating the horizontal gap score ( aka insert shift to first string score)
                    shift_first_score  = SW[i, j - 1] + self.char_scores[ self.char_to_idx["#"], self.char_to_idx[s1[j-1]]]
                    scores[LEFT] = shift_first_score

                    best_score = np.max(scores)

                    tb_action = np.argmax(scores)

                    SW[i][j], TB[i][j] = best_score, tb_action

            GA_score = SW[len(s0), len(s1)]
            return GA_score, SW, TB
            # return self.SW[len(s0), len(s1)]

    # adding gap_penalty to be able to regulate it when needed
    def __init__(self, char_scores:pd.DataFrame, gap_penalty = -1):
        assert char_scores.index.to_list() == char_scores.columns.to_list(), "char_dist is not a square matrix"
        assert '#' not in char_scores.columns.to_list(), "'#' symbol is not allowed in char_dist"

        # '#' means gap
        char_scores['#'] = gap_penalty
        char_scores.loc['#'] = gap_penalty

        self._char_scores = char_scores.copy().to_numpy(dtype=np.float64)
        self._char_to_idx = typed.Dict.empty(
                key_type=types.string, 
                value_type=types.int64
                )
        for idx, char in enumerate(char_scores.index.to_list()):
            self._char_to_idx[char] = idx        
        self.internal = self.uberfast_allign(self._char_scores, self._char_to_idx)
        
    def __call__(self, s0:str, s1:str):
        score, _, _ = self.internal.allign(s0, s1)
        return - score


    def distance_matrix(self, strings:pd.DataFrame ):
        names = strings.index
        strings_numpy = strings.to_numpy(dtype=str)
        print(strings.shape)
        num_iterations = strings.shape[0] * (strings.shape[0] - 1) // 2
        with ProgressBar(total=num_iterations) as progress:
            distances = allign.produce_dist_matrix(self.internal, strings_numpy, progress)
        dist_matrix = pd.DataFrame(
            squareform(distances),
            columns = names,
            index = names
            )
        return dist_matrix

    @staticmethod
    @njit(parallel=True, nogil=True, nopython=True)
    def produce_dist_matrix(internal, strings, progress_proxy):
        n_str = strings.shape[0]
        ans = np.zeros(n_str*(n_str-1) // 2) 
        for i in prange(n_str):
            for j in range(i+1, n_str):
                s1 = str(strings[j])
                s0 = str(strings[i])
                # print(strings[i], (str(strings[j])) )
                score, _, _ = internal.allign(s0, s1)
                ans[ n_str * i - i*(i-1) // 2 + j - i] = - score
                # ans[j,i] = ans[i,j]
            progress_proxy.update(n_str  - i)
        return ans


# slow but understandsable version for experiments
class Trace(IntEnum):
    STOP = 0
    UP = 1
    LEFT = 2
    DIAG = 3

class Alligner:
    """
        This class will be used to make different allignments of two strings.
        It uses analogue of Smith-Waterman and Needleman-Wunsch algorithms.

        Usage:
            1. [optional] Define similarity function. It must take two tokens and return similarity score.
                Default similarity corresponds to edit distance with +1 for same characters and -1 for
                edit, insert and delete actions.
            2. [optional] Define judje function. It must take list of scores for each possible action and 
                current position, and return alligment score, traceback action and block data.
                Default judje corresponds to minimizing total similarity score among current alligment.
                (in future here will be heuristics for large blocks vs low edit distance tradeoff )
            2. Create Alligner object:
                aligner = Alligment(s0, s1, similarity=token_similarity)
            This will automaticly build a matrix of scores and a matrix of traceback actions
            based on provided similarity function
            
            For further usage, yo can:
            1. Get alligment score: alligner.get_allignment_score()
            2. Get global alligned strings: alligner.traceback()
            3. todo: Get blockwise local alligments
            4. todo: Get alligment matrix: alligner.get_alligment_matrix()
            5. todo: Get traceback matrix: alligner.get_traceback_matrix()
            6. todo: Get block count matrix: alligner.get_block_count_matrix()
            7. todo: build a block tree: alligner.get_block_tree() -- for applying tree similarity measures

    """
    
    def __init__( self, s0: str, s1:str, local=False, similarity:callable=None, judje:callable=None):
        """
        :param s0: first string
        :param s1: second string
        :param local: if True, builds best local alligment. global elsewise(not ready yet)
        :param similarity: must be callable function which takes two args (char1, char2) and returns how 
                           similar they are. Note that indel is valued as similarity (char, ' '). 
                           we think rhat new block is started if similarity <= SIMILARITY_BLACK_TRASHHOLD  (?)
        """
        self.score = 0
        self.charset = list(set(s0 + s1))
        self.similarity = lambda x, y: 1 if x == y else -1
        self.s0 = s0 + '#'
        self.s1 = s1 + '@'
        self.local = local
        if similarity is not None:
            self.similarity = similarity
        self.local_maximas = []


        if judje is not None:
            self.judje = judje
        # print(self.SW_matrix)
        # print(self.TB_matrix)
        # print(self.max_index)
        # return self.traceback()
        self.allign(s0, s1)
        if local:
            self.search_local_maximas()


    def get_allignment_score(self):
        s0_diagonal_score = sum([self.similarity(c, c) for c in self.s0[:-1]])
        s1_diagonal_score = sum([self.similarity(c, c) for c in self.s1[:-1]])
        max_posssible_score = min(s0_diagonal_score, s1_diagonal_score)
        min_posssible_score = -len(self.s0) - len(self.s1)
        # print(max_posssible_score, min_posssible_score, self.max_score)
        score = (self.max_score - min_posssible_score) / (max_posssible_score - min_posssible_score)
        assert score >= 0 and score <= 1, "score must be in range [0, 1]"
        return score 
        # todo : return local alligment score for each block


    def judje(self, scores: list, i:int, j:int):
        """
        This function decides, which action is the best. In basic variant, 
        it just compares wealth for insertion, deletion and editing. In future
        will use some block minimization heuristics.
        

        :param scores: list of scores for each possible action
        :param i: row of the current cell
        :param j: column of the current cell
        :return: best score, traceback action, block data
        """

        best_score = max([ scores[k] for k in Trace ])
        tb_action = -1
        block_data = -1

        if best_score == scores[Trace.STOP]:
            tb_action = Trace.STOP
        elif best_score == scores[Trace.DIAG]:
            tb_action = Trace.DIAG
        elif best_score == scores[Trace.UP]:
            tb_action = Trace.UP
        elif best_score == scores[Trace.LEFT]:
            tb_action = Trace.LEFT
            
        # Tracking the cell with the maximum score
        if best_score > self.max_score:
            self.max_index = (i,j)
            self.max_score = best_score

        return best_score, tb_action

    def search_local_maximas(self):
        # tracking local alligment blocks
        for i in range(1, len(self.s0) ):
            for j in range(1, len(self.s1) ):
                scores = []
                for k in [-1, 0, 1]:
                    for l in [-1, 0, 1]:
                        try:
                            scores.append(self.SW_matrix[i+k][j+l])
                        except:
                            continue

                best_score = max(scores)
                if best_score > 0 and self.SW_matrix[i][j] == best_score:
                    self.local_maximas.append((i,j))

    # @numba.jit("float64[:](float64[:], float64[:])", nopython=False, nogil=True)
    def allign(self, s0:str, s1:str, judje=judje):
        """
        Smith-Waterman algorithm for local sequence alignment.
        :param s0: first string
        :param s1: second string
        :param judje: function which takes list of scores for each possible action and returns best score, traceback action, block data
        """

        # Generating the empty matrices for storing scores and tracing
        row = len(s0)+1
        col = len(s1)+1
        # main scores matrixx + block count data
        self.SW_matrix = np.zeros(shape=(row, col), dtype=int) 
        # trace back matrix
        self.TB_matrix = np.zeros(shape=(row, col), dtype=int)

        # Initialising the variables to find the highest scoring cell
        self.max_score = -1
        self.max_index = (-1, -1)
        
        # Calculating the scores for all cells in the matrix
        block_nr = 1
        if not self.local:
            self.SW_matrix[0][0] = 0
            for i in range(1, row):
                self.SW_matrix[i][0] = i * self.similarity(s0[i-1], " ")

            for j in range(1, col):
                self.SW_matrix[0][j] = j * self.similarity(" ", s1[j-1])
        

        for i in range(1, row):
            for j in range(1, col):
                scores = {}
                if self.local:
                    scores[Trace.STOP] = 0
                else:
                    scores[Trace.STOP] = -9999999999999

                # Calculating the diagonal score (match score)
                match_value = self.similarity( s0[i-1], s1[j-1])
                diagonal_score = self.SW_matrix[i - 1, j - 1] + match_value
                scores[Trace.DIAG] = diagonal_score

                # Calculating the vertical gap score  (aka insert shift to second string score)
                shift_second_score = self.SW_matrix[i - 1, j] + self.similarity(s0[i-1], " ")
                scores[Trace.UP] = shift_second_score

                # Calculating the horizontal gap score ( aka insert shift to first string score)
                shift_first_score  = self.SW_matrix[i, j - 1] + self.similarity(" ", s1[j-1])
                scores[Trace.LEFT] = shift_first_score
                                
                # Taking the highest score 
                self.SW_matrix[i][j], self.TB_matrix[i][j] = self.judje(scores, i, j)



    
    def traceback(self,index = None):
        # Initialising the variables for tracing
        aligned_seq1 = ""
        aligned_seq2 = ""   
        current_aligned_seq1 = ""   
        current_aligned_seq2 = ""  
        if self.local:
            if index is not None:
                i, j = index
            else:
                i, j = self.max_index
        else:
            i, j = len(self.s0)-1, len(self.s1)-1
        # i, j = len(self.s0) -2, len(self.s1) - 2

        # Tracing and computing the pathway with the local alignment
        while self.TB_matrix[i][j] != Trace.STOP:
        
            if self.TB_matrix[i][j] == Trace.DIAG:
                current_aligned_seq1 = self.s0[i - 1]
                current_aligned_seq2 = self.s1[j - 1]
                i-= 1
                j-= 1
                      
            elif self.TB_matrix[i][j] == Trace.UP:
                current_aligned_seq1 = self.s0[i - 1]
                current_aligned_seq2 = '-'
                i -= 1
                
            elif self.TB_matrix[i][j] == Trace.LEFT:
                current_aligned_seq1 = '-'
                current_aligned_seq2 = self.s1[j - 1]
                j-=1
                
            aligned_seq1 = aligned_seq1 + current_aligned_seq1
            aligned_seq2 = aligned_seq2 + current_aligned_seq2


        if not self.local:
            assert i == 0 or j == 0, "global alligment finished before string start"
            while i > 0:
                current_aligned_seq1 = self.s0[i - 1]
                current_aligned_seq2 = '-'
                i -= 1
                aligned_seq1 = aligned_seq1 + current_aligned_seq1
                aligned_seq2 = aligned_seq2 + current_aligned_seq2

            while j > 0:
                current_aligned_seq1 = '-'
                current_aligned_seq2 = self.s1[j - 1]
                j -= 1
                aligned_seq1 = aligned_seq1 + current_aligned_seq1
                aligned_seq2 = aligned_seq2 + current_aligned_seq2

        # Reversing the order of the sequences
        aligned_seq1 = aligned_seq1[::-1]
        aligned_seq2 = aligned_seq2[::-1]
        
        return aligned_seq1, aligned_seq2

if __name__ == "__main__":
    s0 = 'hello_world'
    s1 = 'world_hello'

    print("fast alignment test")
    char_list = list("abcdefghijklmnopqrstuvwxyz_0123456789")
    char_score = pd.DataFrame(index=char_list, columns=char_list)
    char_score = char_score.fillna(-1)
    for i in char_score.columns:
        char_score[i].loc[i] = 0
    al = allign(char_score)
    print('fast al compiled')

    print("editdist = ", al(s0,s1) )
    assert 8 == al("hello_world","world_hello"), "error in fast edit distance"
    # print(al.SW)
    assert 3 == al("sitting", "kitten"), "error in fast edit distance"
    # print(al.SW)
    assert 3 == al("sunday", "saturday"), "error in fast edit distance"
    # print(al.SW)
    print("fast alligner seems OK")
    # print(char_score)
    strings = ["hello", "words", "kekek","hello", "words", "kekek","hello", "words", "kekek","hello", "words", "kekek","hello", "words", "kekek","hello", "words", "kekek"]
    dm = pd.DataFrame({"words": strings,
                       "names": [str(i) for i in range(len(strings)) ]
                       })
    dm.set_index('names', inplace=True)
    print(al.distance_matrix(dm['words']))

    print(f"input strings: >{s0}< and >{s1}<")
    print(f"                             lcs: {lcs_heuristic(s0, s1)}")
    print(f"               seq_matcher_ratio: {seq_matcher_ratio_heuristic(s0, s1)}")
    print(f"  parametrized seq_matcher_ratio: {seq_matcher_ratio_heuristic(s0, s1)}")
    alligner = Alligner(s0, s1, local=False)
    print(f"         global alligmment score: {alligner.get_allignment_score()}")
    aligned_seq1, aligned_seq2 = alligner.traceback()
    print(f"global alligmment:")
    print("    >" + aligned_seq1 + "<")
    print("    >" + aligned_seq2 + "<")

    alligner = Alligner(s0, s1, local=True)
    print("smith-waterman matrixx:")
    print(alligner.SW_matrix)
    print("local maximas:")
    print(alligner.local_maximas)
    print("lacal alligmmens:")
    for allign in alligner.local_maximas:
        aligned_seq1, aligned_seq2 = alligner.traceback(allign)
        print(f"alligmment:")
        print("    >" + aligned_seq1 + "<")
        print("    >" + aligned_seq2 + "<")





