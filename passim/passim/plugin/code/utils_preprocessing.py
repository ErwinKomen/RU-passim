#!/usr/bin/env python
# coding: utf-8

import re
import math
from typing import Dict, List, Tuple
import pandas as pd
import numpy as np
from scipy.spatial.distance import squareform, pdist
from tqdm import tqdm
import os
import sqlite3
_DIGITS = re.compile("\d+", re.UNICODE)
_PASSIM_CODE = re.compile(r"PASSIM \d{3}.\d{4}", re.UNICODE)


def year_to_century(year):
    return math.ceil(year / 100)

def _parse_location_start(location_string: str):

    should_reduce = False

    if type(location_string) != str:
        print("Invalid location:", location_string, "setting to 65536")
        return 65536

    if location_string.startswith("?"):
        location_string = location_string.split("-")[1]
        should_reduce = True

    if "-" in location_string:
        location_string = location_string.split("-")[0]

    if location_string == "rear pastedown":
        return 65537

    if location_string == "front paste":
        return -65537

    digits_found = _DIGITS.findall(location_string)

    if len(digits_found) == 0:
        # todo: make smarter
        if ord("A") <= ord(location_string[0]) <= ord("Z"):
            fromm = -100 + ord(location_string[0]) - ord("A")
        elif ord("a") <= ord(location_string[0]) <= ord("z"):
            fromm = -100 + ord(location_string[0]) - ord("a")
        else:
            raise Exception("Unknown enumeration scheme:", location_string)
    else:
        fromm = int(digits_found[0])

    fromm = fromm + 0.5 if "v" in location_string else fromm

    return fromm - 0.5 if should_reduce else fromm


def get_passim_sequences(passim_table: pd.DataFrame, use_order=True, sermons_id="passim_code" ) -> Dict[str, List[str]]:
    """
    :param passim_table: Information about series from the dataframe
    :param use_order: If True, generate sentences by column 'order'. 
        Elsewise parse 'location' column.
    :return: a dictionary: { series_name: [a list of sermons names] }
    """
    
    result = {}

    for series_id_tuple, series_related_data in passim_table.groupby(["country", "city", "library", "shelfmark"]):
        script_name = ", ".join(series_id_tuple)
        print(f"\n{script_name} ---------------")

        
        if not use_order:
            # :TODO
            base_info = [tuple(item) for index, item in
                     series_related_data[["location", "passim_code", "signatures"]].iterrows()]
            # print(base_info)
            
            base_info_sorted = sorted([(_parse_location_start(loc), code, sign) for loc, code, sign in base_info],
                              key=lambda x: x[0])
            # print(base_info_sorted)
        
        else:
            # skip sermos with unindentifed id's
            series_related_data = series_related_data[series_related_data[sermons_id].notna()]
            if sermons_id == "passim_code":
                assert series_related_data[sermons_id].map(lambda x: bool(_PASSIM_CODE.fullmatch(x))).all(),"uncorrect passim code"
            sequence_list = series_related_data.sort_values(by='order')[sermons_id].tolist()
            if len(sequence_list) > 0:
                result[script_name] = sequence_list
        
            

    return result

def get_passim_data_from_db(passim_db: sqlite3.Connection, signature: str = ".*AU s .*", sermon_id = "signatures", filter=False) -> Tuple[Dict[str, List[str]], Dict[str, Dict[str, str]]]:
    """
    Get series content and metadata directly from the database.

    :param passim_db: Connection to the databased of the PASSIM project
    :param signatures: an optional str pattern to filter series by presence of signatures matched by the pattern.
    :param filter: whether apply filtering or not
    :return: a tuple: a dict { series_name: [a list of sermons names] }, a dict {series_name: {matadata_key: piece of metadata}}

    """
    # defining regexp function as it does not directly work in python sqlite3
    def regexp(expr, item):
        try:
            reg = re.compile(expr)
            return reg.search(item) is not None
        except Exception as e:
            # print(f"Error in regexp function: {e}")
            return False

    passim_db.create_function("regexp", 2, regexp)

    # query with optional regexp filtering by query

    passim_db_export_query = f"""WITH manuscript (id, country, city, library, shelfmark, "date") AS
        (
            SELECT
                ms.id,
                sc2.name, c.name, l.name, ms.idno,
                (ms.yearstart || '-' || ms.yearfinish) AS "date"
            FROM seeker_manuscript ms
            LEFT JOIN seeker_library l ON l.id = ms.library_id
            LEFT JOIN seeker_city c ON c.id = l.city_id
            LEFT JOIN seeker_country sc2 on c.country_id = sc2.id
            LEFT JOIN seeker_codico sc ON ms.id = sc.manuscript_id
            WHERE (c.name || ';' || l.name || ';' || ms.idno) IS NOT NULL
            GROUP BY ms.id, c.name, l.name, ms.idno --, ms.yearstart, ms.yearfinish
            ORDER BY COUNT(DISTINCT ms.id) DESC
        ),
        all_sigs (af_id, af_author, af_passim_code, codes) AS
        (
            SELECT
                id,
                name,
                code,
                GROUP_CONCAT(codes_comb, '<SEPARATOR>')
            FROM
            (
                SELECT
                    eg.id,
                    sa.name,
                    eg.code,
                    s.code || '<TYPE-SEP>' || s.editype as codes_comb

                FROM
                    seeker_equalgold AS eg
                LEFT JOIN seeker_sermongold ss ON eg.id = ss.equal_id
                LEFT JOIN seeker_signature s ON ss.id = s.gold_id
                LEFT JOIN seeker_author sa ON eg.author_id = sa.id
                GROUP BY eg.id, sa.name, eg.code, s.code
                ORDER BY
                    CASE
                        WHEN s.editype = "gr" then 1
                        WHEN s.editype = "cl" then 2
                        WHEN s.editype = "ot" then 3
                        ELSE 99
                    END
            )
            GROUP BY id, name, code
        ),
        sigs_for_sermons (id, authority_file, af_link_id, passim_code, signatures) AS
        (
            SELECT
                sd.id,
                se.super_id AS "authority_file",
                se.id as af_link_id,
                "as".af_passim_code AS passim_code,
                "as".codes AS signatures
            FROM seeker_sermondescr sd
            LEFT JOIN seeker_sermondescrequal se ON sd.id = se.sermon_id
            LEFT JOIN seeker_equalgold s ON se.super_id = s.id
            LEFT JOIN all_sigs "as" ON se.super_id = "as".af_id
            WHERE se.super_id IS NOT NULL and passim_code is not null
            ORDER BY se.id, af_link_id
        )
    SELECT
        ms.id as passim_ms_id,
        ms.country, ms.city, ms.library, ms.shelfmark,
        ms.date,
        ss.id,
        ss.locus as location, mi."order",
        sig_serm.authority_file,
        valid_copies.num as num_copies,
        total_texts.num as total_texts,
        -- sig_serm.af_link_id,
        -- sig_serm.id, sig_serm.authority_file, sig_serm.passim_code, sig_serm.signatures
        CASE WHEN sig_serm.signatures is not null THEN sig_serm.signatures ELSE sig_serm.passim_code || '<TYPE-SEP>' END as "signatures"
    FROM manuscript ms
    LEFT JOIN seeker_msitem mi ON ms.id = mi.manu_id
    LEFT JOIN seeker_sermondescr ss ON mi.id = ss.msitem_id
    LEFT JOIN sigs_for_sermons sig_serm ON ss.id = sig_serm.id
    LEFT JOIN (SELECT ms.id as ms_id, count(sig_serm.id) as num
               FROM seeker_manuscript ms
               LEFT JOIN seeker_msitem mi ON ms.id = mi.manu_id
              LEFT JOIN seeker_library l ON l.id = ms.library_id
            LEFT JOIN seeker_city c ON c.id = l.city_id
            LEFT JOIN seeker_country sc2 on c.country_id = sc2.id
    LEFT JOIN seeker_sermondescr ss ON mi.id = ss.msitem_id
    LEFT JOIN sigs_for_sermons sig_serm ON ss.id = sig_serm.id
    WHERE sig_serm.authority_file is not null
    GROUP BY ms.id, c.name, l.name, ms.idno
               )  valid_copies on valid_copies.ms_id = ms.id
    LEFT JOIN (SELECT ms.id as ms_id, count(ss.id) as num
               FROM seeker_manuscript ms
               LEFT JOIN seeker_msitem mi ON ms.id = mi.manu_id
              LEFT JOIN seeker_library l ON l.id = ms.library_id
            LEFT JOIN seeker_city c ON c.id = l.city_id
            LEFT JOIN seeker_country sc2 on c.country_id = sc2.id
    LEFT JOIN seeker_sermondescr ss ON mi.id = ss.msitem_id
    -- LEFT JOIN sigs_for_sermons sig_serm ON ss.id = sig_serm.id
    GROUP BY ms.id, c.name, l.name, ms.idno
               )  total_texts on total_texts.ms_id = ms.id
    WHERE ms.id in (select
    ms.id
    FROM manuscript ms
    LEFT JOIN seeker_msitem mi ON ms.id = mi.manu_id
    LEFT JOIN seeker_sermondescr ss ON mi.id = ss.msitem_id
    LEFT JOIN sigs_for_sermons sig_serm ON ss.id = sig_serm.id
    {f"WHERE sig_serm.signatures regexp '{signature}'" if filter else ""}
    ) and 
    sig_serm.authority_file is not null

    ORDER BY ms.country, ms.city, ms.library, ms.shelfmark, mi."order"
    """
    # export from db (it should be in the data folder, obviously
    passim_table = pd.read_sql_query(passim_db_export_query, passim_db)

    result = {}
    metadata = {}

    # dealing with weird, unrealistic or absent dates
    passim_table["date"] = passim_table["date"].apply(lambda x: x if not ("3000" in x or x is None or "100-100" in x or "1800-2020" in x) else "unknown")

    for j, (series_id_tuple, series_related_data) in enumerate(passim_table.groupby(["country", "city", "library", "shelfmark"])):
        # string row index of the group
        idx_list = series_related_data.index.tolist()

        # creating a brief id of the manuscript
        script_id =f"ms_{j + 1}"

        script_name = ", ".join(series_id_tuple)
        metadata[script_id] = {}

        # getting basic metadata
        library = series_related_data["city"].unique()[0]
        lcity = series_related_data["library"].unique()[0]
        idno = series_related_data["shelfmark"].unique()[0]
        lcountry = series_related_data["country"].unique()[0]
        date = series_related_data["date"].unique()[0]
        passim_ms_id = series_related_data["passim_ms_id"].unique()[0]
        manuscript_id = script_name

        print(f"\n{script_name}; {script_id} ---------------")

        series_related_data = series_related_data[series_related_data[sermon_id].notna()]

        # getting simple signatures identifying each element in the series
        if sermon_id == "signatures":
            first_sigs = []
            all_sigs = []
            for siglist in series_related_data[sermon_id].values.tolist():
                # getting all signatures for future filtering by content
                all_sigs = [s.split("<TYPE-SEP>")[0] for s in siglist.split("<SEPARATOR>")]
                # first simple signature for identification of the element
                first_sig = all_sigs[0]
                # if simple signature is not that simple, shorten it
                if len(first_sig) >= 20:
                    first_sig = first_sig[:17] + '...'
                first_sigs.append(first_sig)
            series_related_data.loc[idx_list, sermon_id] = first_sigs
            print(first_sigs)
            "sermons"
            """
            if it's content of the series, let's create a line describing it to add to hovertext
            line should be like : 
            AU s 109; AU s 54; AU s 55; AU s 61; AU s 62,
            <br>
            AU s 100; AU s 67; AU s 70; AU s 69; AU s 71,
            <br>
            """
            # collecting gryson_codes
            content_line_accum = []

            # preparing 5 text long slices
            for i in range(0, len(first_sigs), 5):
                sermon_group = "; ".join(first_sigs[i:i + 5])  # str with 5 texts
                # again, if a string is too long, split in into several lines
                if len(sermon_group) > 60:
                    sermon_group = f"{'; '.join(sermon_group.split('; ')[0:2])};<br>{'; '.join(sermon_group.split('; ')[2:4])};<br>{'; '.join(sermon_group.split('; ')[4:])}"
                content_line_accum.append(sermon_group)
            sermon_formatted_list = ";<br>".join(content_line_accum)  # final piece of data to add our metadata
            total = len(first_sigs)


            metadata[script_id]["library"] = library
            metadata[script_id]["lcity"] = lcity
            metadata[script_id]["idno"] = idno
            metadata[script_id]["lcountry"] = lcountry
            metadata[script_id]["date"] = date
            metadata[script_id]["total"] = total
            metadata[script_id]["sermons"] = sermon_formatted_list if len(sermon_formatted_list) <= 500 else sermon_formatted_list[:450] + f'({total} sermon in total)'
            metadata[script_id]["content"] = all_sigs # for filtering by content
            metadata[script_id]["ms_identifier"] = manuscript_id
            metadata[script_id]["passim_ms_id"] = passim_ms_id


            # calculating centuries
            if not date == "unknown":
                if '-' in date:  # if date is a range
                    start, end = map(int, date.split('-'))  # convert to integers
                else:  # if date is a single year
                    start = end = int(date)

                median = math.floor((start + end) / 2)
                century = year_to_century(median)

            else:
                century = "unknown"

            assert century is not None

            metadata[script_id]["century"] = century

        sequence_list = series_related_data.sort_values(by='order')[
            sermon_id].tolist()

        if len(sequence_list) > 0:
            result[script_id] = sequence_list

    return result, metadata

def get_passim_core_from_custom_db(passim_db: sqlite3.Connection) -> Tuple[Dict[str, List[str]], Dict[str, Dict[str, str]]]:


    dataset_extraction_query = """WITH manuscript_content (passim_ms_id, country, city, library, shelfmark, ms_identifier, "date", century, sermons) as
    (select
         ms.manuscript_id,
         co.country,
         c.city,
         l.library,
         ms.shelfmark,
         c.city || ', ' || l.library || ', ' || ms.shelfmark as ms_identifier,
         CASE WHEN d.date_text != 'UNKNOWN' THEN d.not_before || '-' ||d.not_after ELSE 'UNKNOWN' END as "date",
         CASE WHEN d.date_text != 'UNKNOWN' THEN d.century ELSE 'UNKNOWN' END as century,
         group_concat(sermons, '<SEPARATOR>')
    from manuscript ms
    JOIN (SELECT manuscript_id, s.gryson_code || '<ORDER_SEPARATOR>' || copy."order" as sermons
          FROM copy
          JOIN sermon s on s.sermon_id = copy.sermon
          JOIN manuscript m on m.manuscript_id = copy.manuscript
          ORDER BY manuscript_id, copy."order") as mm on ms.manuscript_id = mm.manuscript_id
    JOIN library l on l.library_id = ms.library
    JOIN city c on c.city_id = ms.city
    JOIN date d on d.date_id = ms.date
    JOIN country co on co.country_id = c.country

    GROUP BY ms_identifier
        )
SELECT * from manuscript_content
"""

    passim_table = pd.read_sql_query(dataset_extraction_query, passim_db)

    print(passim_table)

    print(passim_table.columns)

    result = {}
    metadata = {}

    for j, (series_id_tuple, series_related_data) in enumerate(passim_table.groupby(["country", "city", "library", "shelfmark"])):

        # string row index of the group
        idx_list = series_related_data.index.tolist()

        # creating a brief id of the manuscript
        script_id =f"ms_{j + 1}"

        script_name = ", ".join(series_id_tuple[1:])
        metadata[script_id] = {}

        # getting basic metadata
        library = series_related_data["library"].unique()[0]
        lcity = series_related_data["city"].unique()[0]
        idno = series_related_data["shelfmark"].unique()[0]
        lcountry = series_related_data["country"].unique()[0]
        date = series_related_data["date"].unique()[0]
        century = series_related_data["century"].unique()[0]
        passim_ms_id = series_related_data["passim_ms_id"].unique()[0]
        manuscript_id = script_name

        print(f"\n{script_name}; {script_id} ---------------")

        series_related_data = series_related_data[series_related_data["sermons"].notna()]

        # getting simple signatures identifying each element in the series
        content = []
        total = 0
        sermon_formatted_list = ""

        for siglist in series_related_data["sermons"].values.tolist():

            # getting all signatures for future filtering by content
            sigs = []
            for s in siglist.split("<SEPARATOR>"):
                sigs.append(s.split("<ORDER_SEPARATOR>")[0])

            print(sigs)

            # first simple signature for identification of the element
            for sig in sigs:
                # if simple signature is not that simple, shorten it
                if len(sig) >= 20:
                    sig = sig[:17] + '...'
                content.append(sig)

            # collecting gryson_codes
            content_line_accum = []

            # preparing 5 text long slices
            for i in range(0, len(content), 5):
                sermon_group = "; ".join(content[i:i + 5])  # str with 5 texts
                # again, if a string is too long, split in into several lines
                if len(sermon_group) > 60:
                    sermon_group = f"{'; '.join(sermon_group.split('; ')[0:2])};<br>{'; '.join(sermon_group.split('; ')[2:4])};<br>{'; '.join(sermon_group.split('; ')[4:])}"
                content_line_accum.append(sermon_group)
            sermon_formatted_list = ";<br>".join(content_line_accum)  # final piece of data to add our metadata
            total = len(content)

            if len(content) > 0:
                result[script_id] = content

        metadata[script_id]["library"] = library
        metadata[script_id]["lcity"] = lcity
        metadata[script_id]["idno"] = idno
        metadata[script_id]["lcountry"] = lcountry
        metadata[script_id]["date"] = date
        metadata[script_id]["total"] = total
        metadata[script_id]["sermons"] = sermon_formatted_list if len(sermon_formatted_list) <= 500 else sermon_formatted_list[:450] + f'({total} sermon in total)'
        metadata[script_id]["content"] = content  # for filtering by content
        metadata[script_id]["ms_identifier"] = manuscript_id
        metadata[script_id]["passim_ms_id"] = passim_ms_id
        metadata[script_id]["century"] = century

    return result, metadata









def get_passim_json(json_dict:dict)-> Dict[str, List[str]]:
    """
    :param json_dict: Information about series from the data file
    :return: a dictionary: { series_name: [a list of sermons names] }
    """

    result = {}
    metadata = {}
    print(len(json_dict))
    for script_name in tqdm(json_dict):

        # print(f"\n{script_name} ---------------")
        script_metadata = json_dict[script_name]
        if "msitems" not in script_metadata or script_metadata["msitems"] is None or len(script_metadata["msitems"]) == 0:
            print("No msitems in", script_name)
        else:
            assert script_name not in result, f"repeating serie name {script_name}"
            result[script_name] = []
            for i, serie in enumerate(script_metadata['msitems']):
                # print(serie)
                assert serie['order'] == i+1, "mekh"            
                result[script_name].append(serie['sermon']['signaturesA'])
            metadata[script_name] = {}
            metadata[script_name]["ms_identifier"] = f"{script_metadata['lcity']}, {script_metadata['library']}, {script_metadata['idno']}"



            for key in script_metadata:
                additional_data = None # for cases where one key gives metadata for more than one columns
                metadata_column_name = key
                metadata_to_add = script_metadata[key] # just copying metadata, base scenario, if there is a nested structure to parse, we'll overwrite it
                if key == "date":
                    # we need to create a new column for century as well
                    def year_to_century(year):
                        return math.ceil(year / 100)

                    century = None

                    # first, dealing with bad values
                    if metadata_to_add in ["Unknown", "?", ""]:
                        century = "unknown" # century
                        metadata_to_add = "unknown" # normalizing unknown dates

                    if not metadata_to_add == "unknown":
                        if '-' in metadata_to_add:  # if date is a range
                            start, end = map(int, metadata_to_add.split('-'))  # convert to integers
                        else:  # if date is a single year
                            start = end = int(metadata_to_add)

                        median = math.floor((start + end) / 2)
                        century = year_to_century(median)

                    assert century is not None

                    additional_data = ("century", century)

                if key == 'msitems':


                    metadata_column_name = "sermons"
                    """
                    if it's content of the series, let's create a line describing it to add to hovertext
                    line should be like : 
                    AU s 109; AU s 54; AU s 55; AU s 61; AU s 62,
                    <br>
                    AU s 100; AU s 67; AU s 70; AU s 69; AU s 71,
                    <br>
                    """
                    # collecting gryson_codes
                    sermons = [srmn["sermon"]["signaturesA"] for srmn in script_metadata[key]]
                    metadata[script_name]["total"] = len(sermons)
                    metadata[script_name]["content"] = sermons

                    content_line_accum = []

                    # preparing 5 text long slices
                    for i in range(0, len(sermons), 5):
                        sermon_group = "; ".join(sermons[i:i+5]) # str with 5 texts
                        if len(sermon_group) > 60:
                            sermon_group = f"{sermon_group.split('; ')[0:2]};<br>{sermon_group.split('; ')[2:4]};<br>{sermon_group.split('; ')[4:]}"
                        content_line_accum.append(sermon_group)

                    metadata_to_add = ";<br>".join(content_line_accum) # final piece of data to add

                    # alternative comprehension
                    # metadata_to_add = ",<br>".join(["; ".join([srmn["sermon"]["signaturesA"] for srmn in script_metadata[key]][i:i+5]) for i in range(0, len([srmn["sermon"]["signaturesA"] for srmn in script_metadata[key]]), 5)])

                metadata[script_name][metadata_column_name] = metadata_to_add
                if additional_data:
                    metadata[script_name][additional_data[0]] = additional_data[1]

    return result, metadata



def get_omeliari_sequences(json_dict: dict) -> Dict[str, List[str]]:
    """
    :param json_dict: Information about series from the data file
    :return: a dictionary: { series_name: [a list of sermons names] }
    """

    result = {script_name: [] for script_name in json_dict}

    for script_name in json_dict:

        print(f"\n{script_name} ---------------")
        script_metadata = json_dict[script_name]

        for fragment in script_metadata:

            # todo: some fragments don't have 'works' section; no other copies are known?
            if "works" not in script_metadata[fragment] or script_metadata[fragment]["works"] is None:
                print("No 'works' in", script_name, fragment)
            else:
                for original_piece in script_metadata[fragment]["works"]:

                    # todo: some works' names are not given, what does that mean?
                    # todo: none are known? no possible other mentions in this corpus?
                    if "Autore/Opera" in original_piece:
                        result[script_name].append(original_piece["Autore/Opera"])
                    else:
                        print("Source name not provided for:", str(original_piece)[:120])
                        # todo: what do we do here?
                        # script_originals_dict["NotProvided"] += 1
    return result


def get_sermons_distance( LDA:pd.DataFrame, work2code=None, dist='cosine') -> pd.DataFrame:
    """
    :param LDA -- matrix of sermons embeddings of shape (sermons, lda_dim)
    :param work2code -- list of sermons names
    :param dist -- distance metric (for scipy pdist)
    :return: matrix of distances between sermons
    """
    # new column names & index are specified in work2code dict 
    if work2code == None:
        work2code = { work_name:work_name for work_name in LDA.index }
    codes = LDA.index.to_series().apply(lambda x: work2code[x])

    sermons_dist= pd.DataFrame(
        squareform(pdist(LDA, dist)), # another metric can be set
        columns = codes,
        index = codes
    )

    return sermons_dist


if __name__ == "__main__":
    current_dir = os.path.realpath(os.path.dirname(__file__))
    import json
    import seaborn as sns
    # csv passim    
    # passim_dataframe = pd.read_csv(os.path.join(current_dir, "../data/mss_dataset.tsv"), sep="\t")
    # print("Passim size:", passim_dataframe.shape)
    # # print(passim_dataframe.head(20))
    # print(passim_dataframe.columns)
    #
    # # print(get_passim_sequences(passim_dataframe))
    #
    # # json omeliari
    # with open(os.path.join(current_dir,"../data/omeliari_by_ms_7_august_2022.json"), "r+", encoding="utf-8") as rf:
    #     json_data = json.load(rf)
    # result = get_omeliari_sequences(json_data)
    # # print(result)
    #
    # # json passim
    #
    # # re-encoding to utf-8-sig
    # with open(os.path.join(current_dir,"../data/sermones_file_dataset_passim_final.json"), "r+", encoding="utf-8") as rf:
    #     lines = rf.readlines()
    #     lines = [ line.encode().decode('utf-8-sig') for line in lines ]
    # with open(os.path.join(current_dir,"../data/sermones_file_dataset_passim_final_.json"), "w", encoding="utf-8") as rf:
    #     rf.writelines(lines)
    # with open(os.path.join(current_dir,"../data/sermones_file_dataset_passim_final_.json"), "r+", encoding="utf-8") as rf:
    #     json_data = json.load( rf )
    #
    # result = get_passim_json(json_data)
    # print(result)
    #
    # # sermons distance
    # os.makedirs(os.path.join(current_dir,"../preprocessed_data/passim2"), exist_ok=True)
    # LDA = pd.read_csv(os.path.join(current_dir,"../data/sermon_topics_from_weighted_paragraphs.tsv"), sep="\t")
    # LDA.set_index("text_id", inplace=True)
    # # LDA = LDA.iloc[:5]
    # LDA = LDA.drop(columns=["passim", "kw", "hc", "mss", "feast", "feast_category", "popularity", "maurini"])
    # dist = get_sermons_distance(LDA,dist="cosine")
    #
    # sns.set(rc={'figure.figsize':(20,20)})
    #hist
    # mean_dist_to_others = dist.mean(axis=1)
    # ax = mean_dist_to_others.hist(bins=15)
    # fig2 = ax.get_figure()
    # fig2.savefig(os.path.join(current_dir,'../output/passim2/sermons_distance_hist.png'))

    # # heatamap
    # hm = sns.heatmap(dist,yticklabels=False,xticklabels=False)
    # fig = hm.get_figure()
    # fig.savefig(os.path.join(current_dir,"../output/passim2/sermons_distance.png"))

    get_passim_data_from_db(sqlite3.connect(os.path.join(current_dir, "../data/passim.db")))
    #get_passim_core_from_custom_db(sqlite3.connect(os.path.join(current_dir, "../data/passim_core.db")))







