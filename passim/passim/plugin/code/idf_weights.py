import sqlite3
import os
from sklearn.feature_extraction.text import TfidfVectorizer
import re
import numpy as np


from utils_preprocessing import get_passim_core_from_custom_db



current_dir = os.path.realpath(os.path.dirname(__file__))

script2works, metadata = get_passim_core_from_custom_db(
        sqlite3.connect(os.path.join(current_dir, "/Users/glebschmidt/Documents/PycharmProjects/alcollsim/alsollsim/data/passim_core.db")))

# Your dictionary


# Convert the list of strings in your dict to a single string
data = {k: ' '.join([re.sub("\s", "_", c) for c in v]) for k, v in script2works.items()}

# print(data)
docs = ['剧 剨', '乬 剩 乮 剪 剫 凅 乞 丸 仍 仏 仐 俦 仓 俨 俩 剬 仔 剭 佯 剮 偟 低 偠 住 偡 佒 偣 体 佖 佗 偳 副 仠 上 剰 剱 割 剳 剴 傓 仁 傔 傄 剺 剻 剼 剽 剾 剿 剿 俷 丏 俻 丑 俺 丕 倶 丛 丘 倸 倀 劀 倂 丝 冇 劁 丞 仩 丠 仪 冈 兛 亠 劂 亡 亣 交 丫 亥 丬 劃 倃 丵 丮 丰 丱 丳 劄 乶 主 兡 劅 互 劆 丽 劇 亡 严 劈 亣剨 刹 傡 俷 冇 劖 剧 劗 劃 劘 劂 劙 俺 丨 冊 亣 劚 力 交 劜 丫 劝 办 亥 丠 功 丬 先 加 务 仯 劢 劣 丰 串 凵 丳 临 仫 丶']
# Create the Document List
documents = list(data.values())
documents = docs

print(documents)

# Create the tf-idf vectorizer object
vectorizer = TfidfVectorizer(analyzer = 'char', lowercase=False)

# Perform the tf-idf transformation
vectorizer.fit_transform(documents)

# Get the names of the features
feature_names = vectorizer.get_feature_names_out().tolist()

print(feature_names)

# Calculate IDF values
idf_values = vectorizer.idf_

# # Normalize IDF values to range [0,1]
# min_idf, max_idf = np.min(idf_values), np.max(idf_values)
# idf_values = (idf_values - min_idf) / (max_idf - min_idf)

# Create a dictionary to store the idf values of each word
idf_dict = {word: idf for word, idf in zip(feature_names, idf_values)}

print(idf_dict)

for k, v in sorted(idf_dict.items(), key=lambda x: x[1]):
    print(f"{k}:\t{v}")


# # Perform the tf-idf transformation
# tfidf_matrix = vectorizer.fit_transform(documents)
#
# # Get the names of the features
# feature_names = vectorizer.get_feature_names_out().tolist()
#
# # Create a dictionary to store total tf-idf value and count of each word
# word_tfidf_dict = {word: {"total_tfidf": 0, "count": 0} for word in feature_names}
#
# # Calculate total tf-idf value and count of each word
# for i, doc in enumerate(documents):
#     for word in doc.split():
#         tfidf_score = tfidf_matrix[i, feature_names.index(word)]
#         word_tfidf_dict[word]["total_tfidf"] += tfidf_score
#         word_tfidf_dict[word]["count"] += 1
#
# # Calculate average tf-idf value of each word
# for word in word_tfidf_dict:
#     word_tfidf_dict[word] = word_tfidf_dict[word]["total_tfidf"] / word_tfidf_dict[word]["count"]
#
# print(len(word_tfidf_dict))
#
# for k, v in sorted(word_tfidf_dict.items(), key=lambda x: x[1], reverse=True):
#     print(f"{k}:\t{v}")
#
# print(word_tfidf_dict["AU_s_351"])
# print(word_tfidf_dict["AU_s_104"])
# print(word_tfidf_dict["AU_s_374"])
# print(word_tfidf_dict["AU_s_46"])
# print(word_tfidf_dict["AU_s_202"])


