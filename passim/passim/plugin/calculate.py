"""
This hosts the calculations for the 'dashboard' plugin originally created by Gleb Schmidt.
Adaptation for Passim: Erwin R. Komen, 2024
"""
import os
import json
import re

# Any plotly imports
import plotly
import plotly.express as px
import plotly.graph_objs as go
import plotly.figure_factory as ff

from collections.abc import Mapping

import pandas as pd

# This is not used import seaborn as sns
from itertools import cycle
from scipy.cluster.hierarchy import *
from umap.umap_ import UMAP

# Imports from passim itself
from passim.settings import PLUGIN_DIR
from passim.plugin.models import BoardDataset
from passim.utils import ErrHandle

# Make sure we have the 'store' available to all
store = {}

# ========================= HELPER FUNCTIONS ========================================
def absjoin(*paths):
    combi = os.path.abspath(os.path.join(*paths))
    return combi

def sort_key(s):
    """Define the sorting key function"""
    pattern = re.compile('.*(\d{1,3}?).*')
    match = pattern.search(s)
    return (int(match.group(1)))

def plotly_heatmap( distances:pd.DataFrame, title:str = "", save_as:str=None, hoverinfo=None, text=None ):
    fig = go.Figure()
    fig.update_layout(width=800, height=800)

    oErr = ErrHandle()
    try:
        # The following code could go wrong, but that is by intention
        #  It will be taken up again in the except part
        try:
            distances.index = distances.index.to_series().apply( lambda x: int(x.split("_")[1]) )
            distances.sort_index(axis=0, ascending=True, inplace=True)
            distances.index = distances.index.to_series().apply( lambda x: "ms_"+str(x) )
        
            distances.columns = distances.columns.to_series().apply( lambda x: int(x.split("_")[1]) )
            distances.sort_index(axis=1, ascending=True, inplace=True)
            distances.columns = distances.columns.to_series().apply( lambda x: "ms_"+str(x) )

            if text is not None:
                text.index = text.index.to_series().apply( lambda x: int(x.split("_")[1]) )
                text.sort_index(axis=0, ascending=True, inplace=True)
                text.index = text.index.to_series().apply( lambda x: "ms_"+str(x) )

                text.columns = text.columns.to_series().apply( lambda x: int(x.split("_")[1]) )
                text.sort_index(axis=1, ascending=True, inplace=True)
                text.columns = text.columns.to_series().apply( lambda x: "ms_"+str(x) )


        except:
            distances.sort_index(axis=0, ascending=True, inplace=True)
            distances.sort_index(axis=1, ascending=True, inplace=True)
            if text is not None:
                text.sort_index(axis=0, ascending=True, inplace=True)
                text.sort_index(axis=1, ascending=True, inplace=True)
            

        if text is None or hoverinfo is None:
            fig.add_trace(go.Heatmap(z=distances,
                                     x=distances.columns,
                                     y=distances.columns,
                            ))
        else:
            fig.add_trace(go.Heatmap(z=distances,
                                     x=distances.columns,
                                     y=distances.columns,
                                     hoverinfo=hoverinfo,
                                     text=text
                            ))
    

        fig.update_layout(
            title=title
        )
    except:
        msg = oErr.get_error_message()
        oErr.DoError("plotly_heatmap")

    return fig

def fill_store(bForce = False):
    """Fill the [store] global variable with datasets"""

    global store
    oErr = ErrHandle()
    preproc_data_dir = absjoin(PLUGIN_DIR, "preprocessed_data")
    try:
        # Do we need to proceed?
        if not bForce and len(store) > 0:
            return None
        # Walk all available dataset
        for obj in BoardDataset.objects.all():
            # Check if there is name/distances/Uniform
            check_path = absjoin(preproc_data_dir, obj.location, "distances", "Uniform")
            bNeedSaving = False
            if os.path.exists(check_path):
                if obj.status != "act":
                    obj.status = "act"
                    bNeedSaving = True
            else:
                if obj.status != "ina":
                    obj.status = "ina"
                    bNeedSaving = True
            if bNeedSaving: obj.save()

            # Check if we can actually load this one
            if obj.status == "act":
                # Yes, it is active
                dataset = obj.location
                store[dataset] = series_data(dataset)
    except:
        msg = oErr.get_error_message()
        oErr.DoError("fill_store")


# ================== Classes for calculations =====================================


class LazyLoader(Mapping):
    def __init__(self, folder, keys, index):
        self.folder = folder
        self._keys = keys
        self.index = index
        assert os.path.isdir(folder)
        self._raw_dict = {}

    def __getitem__(self, key):
        assert key in self._keys
        if key not in self._raw_dict:
            print("A key here", key, self._keys)
            self._raw_dict[key] = self.load(key)
        return self._raw_dict[key]

    def load(self, name):
        print("Printing name", name)
        return pd.read_csv(absjoin(self.folder, name + '.csv')).set_index(self.index)

    def __iter__(self):
        return iter(self._raw_dict)

    def __len__(self):
        return len(self._raw_dict)

    def keys(self):
        return self._keys


class series_data:

    preproc_data_dir = absjoin(PLUGIN_DIR, "preprocessed_data")

    def __init__(self, name=None):
        def extract_age(date, by_first=True):
            if not str(date).split("-")[0].isnumeric():
                return float('nan')
            else:
                return float(int(str(date).split("-")[0]) // 100)

        if name is not None:
            oErr = ErrHandle()
            try:
                self.id                 = name
                self.main_dir           = absjoin(self.preproc_data_dir, name)
            
                self.char_dist_dir      = absjoin(self.main_dir, "char_distances")
                self.char_dist_names    = [ name.split('.')[0] for name in os.listdir(self.char_dist_dir) ] + ['Uniform']
                self.char_distances     = LazyLoader(self.char_dist_dir, self.char_dist_names, 'text_id')
            
            
                self.serie_distances    = {}
                self.serie_dist_names   = {}
                for serm_distance in self.char_dist_names:

                    serie_dist_dir      = absjoin(self.main_dir, f"distances/{serm_distance}")
                    self.serie_dist_names[serm_distance]    = [ name.split('.')[0] for name in os.listdir(serie_dist_dir) ]
                    self.serie_distances[serm_distance]     = LazyLoader(serie_dist_dir, self.serie_dist_names[serm_distance], 'SeriesName')
            
                self.char_codes         = pd.read_csv(absjoin(self.main_dir, 'char_codes.csv')).set_index("SermonName")

                self.char_series        = pd.read_csv(absjoin(self.main_dir, 'char_series.csv')).set_index("SeriesName")
            except:
                msg = oErr.get_error_message()
                oErr.DoError("series_data/init")
            try:
                oErr.Status("series_data metadata...")
                self.metadata       = pd.read_csv(absjoin(self.main_dir, 'metadata.csv')).set_index("SeriesName")
                self.metadata["age"]   = self.metadata.date.apply( extract_age )
                oErr.Status("series_data metadata attempt #1")
            except:
                try:
                    self.metadata       = pd.read_csv(absjoin(self.main_dir, 'metadata.csv')).set_index("SeriesName")
                    oErr.Status("series_data metadata attempt #2")
                except:
                    self.metadata       = pd.DataFrame(index=self.char_series.index)
                    oErr.Status("series_data metadata attempt #3")


            # to Gleb:  you can add here anything you want. For your idea with highlighting emblematic series,
            #           for example, you can add a column "is_emblematic" and color by it. Here is code for
            #           such example.
            emblematic = ["ms_32", "ms_3104", "ms_1404"]
            self.metadata['is_emblematic'] = self.metadata.index.to_series().apply(lambda x: x in emblematic)


            # for column in metadata.columns():
                # removing redundant metadata (with 1 unique value or empty)               

            self.series_list        = list(self.char_series.index)

    def get_serie_hm_hovertext(self, matrix):

        # to Gleb: feel free to modificate for your purpose!
        # it gets a two series ids's (from SeriesName index)
        # and gives a string which is shoved in series heatmap

        template="""
{0}   x   {1}<br />
Distance: {2}<br />
more important info about this two series???
        """
        hovertext = matrix.copy()
        for y in matrix.index:
            for x in matrix.columns:
                dist=matrix[y].loc[x]
                hovertext[y].loc[x] = template.format(y, x, dist)
        return hovertext

    def get_clustering_hovertext(self, matrix):
        # names in {} must exactly match the metadata column names
        template="""
        ms_id:   {ms_id}<br />
        lcountry:   {lcountry}<br />
        lcity:      {lcity}<br />
        date:       {date}<br />
        library:    {library}<br />
        idno:       {idno}<br />
        Contents:<br />       {sermons}<br />
        """

        """Anything else? feel free to add :)<br />
         just follow the template, <br />
         you don't even need to change the code"""
        hovertext = pd.DataFrame(index = matrix["SeriesName"])
        def gen_text(row):
            val = {col: row[col] for col in row.index.tolist()}
            # print(val)
            return template.format(**val)

        # index copied as a metadata column
        self.metadata["ms_id"] = self.metadata.index.to_series()

        hovertext['text'] = self.metadata.apply(gen_text, axis=1)
        return hovertext

    def get_umap_hovertext(self, matrix):
        # names in {} must exactly match the metadata column names
        template="""
        ms_id:   {ms_id}<br />
        lcountry:   {lcountry}<br />
        lcity:      {lcity}<br />
        date:       {date}<br />
        library:    {library}<br />
        idno:       {idno}<br />
        Contents:<br />       {sermons}<br />
        """

        """Anything else? feel free to add :)<br />
         just follow the template, <br />
         you don't even need to change the code"""
        hovertext = pd.DataFrame(index = matrix["SeriesName"])
        def gen_text(row):
            val = {col: row[col] for col in row.index.tolist()}
            # print(val)
            return template.format(**val)

        # index copied as a metadata column
        self.metadata["ms_id"] = self.metadata.index.to_series()

        hovertext['text'] = self.metadata.apply(gen_text, axis=1)
        return hovertext

    def __str__(self):
        cd  = '\n                   '.join( self.char_distances.keys() )
        sd = ""
        for i in self.char_dist_names:
            sd+= f'\n                   ==== {i} ====\n                   '
            sd+= '\n                   '.join( self.serie_distances[i].keys() )   

        mdc = "\n                   ".join(self.metadata.columns)
        return f"""
               id: {self.id}
----------------------------------------------------------------
   char distances: {cd}
----------------------------------------------------------------
  serie distances: {sd}
----------------------------------------------------------------
     total series: {len(self.series_list)}
----------------------------------------------------------------
    metadata cols: {mdc}
    """


class GenGraph(object):
    global store

    local_store = None
    local_graph_store = {}
    reset_length = False

    def __init__(self, dic_this=None, dic_store=None):
        self.local_graph_store = {}
        self.reset_length = False
        oErr = ErrHandle()
        try:
            # Try to fill the store if it has not yet been filled
            fill_store()
            # Set my own local store pointing to the global one
            self.local_store = store
            # Process parameter [dic_this]
            if not dic_this is None:
                self.set_local_graph(dic_this)
            # Process parameter [dic_store]
            if not dic_store is None:
                self.set_store(dic_store)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("GenGraph")

    def set_local_graph(self, dic_this):
        if not dic_this is None and isinstance(dic_this,dict):
            for k,v in dic_this.items():
                self.local_graph_store[k] = v

    def set_store(self, dic_this):
        if not dic_this is None and isinstance(dic_this,dict):
            for k,v in dic_this.items():
                self.local_store[k] = v

    def set_reset_length(self, bValue):
        self.reset_length = bValue

    def generate_graphs(self, arg_dic):
        """
        This callback generates three simple graphs from random data.
        """
        # OLD: global local_graph_store, store, reset_length

        def check_series(dataset, serdist, sermdist):
            oErr = ErrHandle()
            msg = ""
            try:
                # Check if this dataset can handle the sermons distance
                if sermdist in self.local_store[dataset].char_dist_names:
                    # Check if the Series distance are in line with the chosen Sermons distance
                    series_keys = self.local_store[dataset].serie_distances[sermdist].keys()
                    if not serdist in series_keys:
                        # Complain about this
                        msg = "Sermons distance [{}] requires Series distance in: {}".format(sermdist, series_keys)
                else:
                    msg = "Dataset [{}] can only handle these sermon distances: {}".format(dataset, self.local_store[dataset].char_dist_names)
            except:
                msg = oErr.get_error_message()
                oErr.DoError("check_series")
            return msg

        # adding filtering by content (for now, mere presence of all the specified sermons)
        def all_sermons_present(content, desired_sermons):
            keep = True
            # print(content)
            for serm in desired_sermons:
                # print(store[dataset].char_codes.loc[serm])
                if not self.local_store[dataset].char_codes.loc[serm]["Code"] in content:
                    keep = False
                    break
            return keep

        oErr = ErrHandle()
        msg = ""
        try:
            # Convert the dictionary to actual parameters
            active_tab = arg_dic.get("active_tab")
            dataset = arg_dic.get("dataset")
            serdist = arg_dic.get("serdist")
            sermdist = arg_dic.get("sermdist")
            method = arg_dic.get("method")
            min_length = int(arg_dic.get("min_length"))
            umap_dim = arg_dic.get("umap_dim")
            umap_hl = arg_dic.get("umap_hl")
            contains = arg_dic.get("contains")
            anchor_ms = arg_dic.get("anchor_ms")
            nb_closest = arg_dic.get("nb_closest")
            umap_md = arg_dic.get("umap_md")
            umap_nb = arg_dic.get("umap_nb")

            # Clear the 'current' item
            self.local_graph_store['current'] = ""

            if dataset is None:
                # generate empty graphs when app loads
                return self.local_graph_store, ""

            msg = check_series(dataset, serdist, sermdist)
    
            if msg == "" and serdist is not None:
                # todo: lazy loading

                long_serie = self.local_store[dataset].char_series['EncodedWorks'].apply(lambda x: len(x) >= min_length and all_sermons_present(x, contains) if contains and len(contains) > 0 else len(
                    x) >= min_length)
                dist_matrix = self.local_store[dataset].serie_distances[sermdist][serdist].loc[long_serie, long_serie]
                
                # if anchor manuscript is given, we need to update our dist_matrix
                if anchor_ms:
                    anchor_ms_idx = self.local_store[dataset].metadata[self.local_store[dataset].metadata["ms_identifier"] == anchor_ms].index.tolist()
                    # in length of anchor manuscript is less than minimal lenght of the series,
                    # setting minimal length to length of the anchor ms (see callback above)
                    try:
                        closest_mss_idx = dist_matrix[anchor_ms_idx[0]].sort_values(ascending=True).head(nb_closest).index.tolist()
                    except KeyError:
                        reset_length = True
                        anchor_ms_length = self.local_store[dataset].metadata.loc[anchor_ms_idx[0]]["total"]
                        long_serie = self.local_store[dataset].char_series['EncodedWorks'].apply(
                            lambda x: len(x) >= anchor_ms_length)
                        dist_matrix = self.local_store[dataset].serie_distances[sermdist][serdist].loc[long_serie, long_serie]
                        closest_mss_idx = dist_matrix[anchor_ms_idx[0]].sort_values(ascending=True).head(
                            nb_closest).index.tolist()

                    dist_matrix = dist_matrix.loc[closest_mss_idx, closest_mss_idx]

                if active_tab == 'hm_series':
                    hovertext = self.local_store[dataset].get_serie_hm_hovertext(dist_matrix)
                    self.local_graph_store['hm_series'] = plotly_heatmap(
                        dist_matrix,
                        hoverinfo='text',
                        text=hovertext
                        )

                    # Set the current graph
                    self.local_graph_store['current'] = self.local_graph_store['hm_series']

                if active_tab == 'clusters':

                    # creating labels for dendrogram
                    clustering_metadata = self.local_store[dataset].metadata[self.local_store[dataset].metadata.index.isin(dist_matrix.index)]
                    clustering_metadata["SeriesName"] = clustering_metadata.index
                    hovertext = self.local_store[dataset].get_clustering_hovertext(clustering_metadata)

                    clustering_df = dist_matrix

                    clustering_df["SeriesName"] = clustering_df.index
                    clustering_df = pd.concat([clustering_df.set_index("SeriesName"), clustering_metadata], axis=1)
                    clustering_df = pd.concat([clustering_df.set_index("SeriesName"), hovertext], axis=1)
                    clustering_df["SeriesName"] = dist_matrix.index

                    clustering_df["ms_identifier"] = clustering_df.apply(lambda row: f"{row['ms_identifier']} ({row['century']})", axis=1)

                    self.local_graph_store['clusters'] = ff.create_dendrogram(dist_matrix.iloc[:, :clustering_df.shape[0]],
                                                                                  linkagefun=lambda x: linkage(x, method),
                                                                                  orientation='left',
                                                                                  labels=clustering_df.ms_identifier,
                                                                                  )

                    self.local_graph_store['clusters'].update_layout(width=800, height=800)

                    # Set the current graph
                    self.local_graph_store['current'] = self.local_graph_store['clusters']

                if active_tab == 'umap':
                    n_components = 2 if umap_dim == '2D' else 3
                    umap_= UMAP(
                        n_components = n_components,
                        min_dist=umap_md,
                        n_neighbors=umap_nb,
                        init='random', 
                        random_state=123, 
                        metric='precomputed'
                        )

                    if len(umap_hl) == 1 and umap_hl[0] in self.local_store[dataset].metadata.columns.tolist():
                        color_col = umap_hl[0]
                        cont_coloring = True
                        if self.local_store[dataset].metadata[color_col].dtype != 'float':
                            cont_coloring = False
                            colorize = {x:x for x in self.local_store[dataset].metadata[umap_hl[0]].unique().tolist()}
                    else:            
                        cont_coloring = False
                        color_col = "SeriesName"
                        # getting index from actual ms_identifiers
                        mask = (self.local_store[dataset].metadata["ms_identifier"].isin(umap_hl))
                        umap_hl = self.local_store[dataset].metadata.index[mask]

                        colorize = {x:x for x in umap_hl}

                    # go_colors = cycle(plotly.colors.sequential.Viridis)
                    go_colors = cycle(px.colors.qualitative.Dark24)

                    proj = umap_.fit_transform(dist_matrix)
                    proj_df = pd.DataFrame(proj) 

                    # print(store[dataset].metadata.shape)
                    proj_df["SeriesName"] = dist_matrix.index
                    proj_df = pd.concat( [ proj_df.set_index("SeriesName"), self.local_store[dataset].metadata], axis=1)
                    proj_df["SeriesName"] = proj_df.index

                    hovertext = self.local_store[dataset].get_umap_hovertext(proj_df)

                    if not cont_coloring:
                        # changing ms_id to actual shelfmark; of course, for publication one should generalize and write a proper mapper, if needed
                        if color_col == "SeriesName":
                            proj_df['color'] = proj_df[color_col].apply(lambda x: proj_df.loc[colorize[x]]["ms_identifier"] if x in colorize else "other")
                        else:
                            proj_df['color'] = proj_df[color_col].apply(lambda x: colorize[x] if x in colorize else "other")
                    else:
                        proj_df['color'] = proj_df[color_col]
                    proj_df['text'] = hovertext['text']

                    fig = go.Figure()
                    fig.update_layout(width=800, height=800)

                    # adding correct descending sorting if color column is "century"
                    color_descrete_values = proj_df.color.unique()

                    for v in color_descrete_values:
                        if v == "other": continue

                    if color_col == "century":
                        color_descrete_values = sorted(proj_df.color.unique(), key=lambda x: int(x) if x.isnumeric() else 0,
                                                       reverse=True)
                    if n_components == 2:
                        if not cont_coloring:
                            for s in color_descrete_values:
                                p_df = proj_df[proj_df.color == s]

                                fig.add_trace(go.Scatter(
                                    x=p_df[0], 
                                    y=p_df[1], 
                                    marker_color=next(go_colors),
                                    # hoverinfo='text',
                                    name=str(s),
                                    customdata=p_df.text,
                                    mode='markers',
                                    hovertemplate='%{customdata}'
                                    # customdata=proj_df.text,
                                    # hovertemplate="%{custom_data}"
                                    )
                                )
                        else:
                            fig.add_trace(go.Scatter(
                                    x=proj_df[0], 
                                    y=proj_df[1], 
                                    marker_color=proj_df.color,
                                    # hoverinfo='text',
                                    customdata=proj_df.text,
                                    mode='markers',
                                    hovertemplate='%{customdata}'
                                    # customdata=proj_df.text,
                                    # hovertemplate="%{custom_data}"
                                    )
                                )
                    else:
                        if not cont_coloring:
                            for s in color_descrete_values:
                                p_df = proj_df[proj_df.color == s]

                                fig.add_trace(go.Scatter3d(
                                    x=p_df[0], 
                                    y=p_df[1], 
                                    z=p_df[2],
                                    marker_color=next(go_colors),
                                    # hoverinfo='text',
                                    name=str(s),
                                    customdata=p_df.text,
                                    mode='markers',
                                    hovertemplate='%{customdata}'
                                    # customdata=proj_df.text,
                                    # hovertemplate="%{custom_data}"
                                    )
                                )
                        else:
                            fig.add_trace(go.Scatter3d(
                                    x=proj_df[0], 
                                    y=proj_df[1],
                                    z=proj_df[2],
                                    marker_color=proj_df.color,
                                    # hoverinfo='text',
                                    customdata=proj_df.text,
                                    mode='markers',
                                    hovertemplate='%{customdata}'
                                    # customdata=proj_df.text,
                                    # hovertemplate="%{custom_data}"
                                    )
                                )
                    self.local_graph_store['umap'] = fig
                    self.local_graph_store['umap'].update_traces(marker_size=5)
                    self.local_graph_store['umap'].update_layout(width=800, height=800)

                    # Set the current graph
                    self.local_graph_store['current'] = self.local_graph_store['umap']
    
            if msg == "" and active_tab == 'hm_sermons':
        
                # Check if all is in order:
                if sermdist is None:
                    msg = "Sermons Heatmap: first specify the sermons distance"
                elif sermdist == "Uniform":
                    msg = "Sermons Heatmap: the sermons distance may *NOT* be 'Uniform'"
                else:
                    # Re-initialize the local_store
                    fill_store(True)

                    # Only now can we continue
                    dist_matrix =  self.local_store[dataset].char_distances[sermdist]
                    rename      =  self.local_store[dataset].char_codes
                    rename["SermonName"] = rename.index
                    rename.set_index("Code", inplace=True)
                    dist_matrix.rename(
                        columns= lambda x: rename["SermonName"].loc[x],
                        index  = lambda x: rename["SermonName"].loc[x],
                        inplace=True
                        )

                    self.local_graph_store['hm_sermons'] = plotly_heatmap(dist_matrix)

                    # Set the current graph
                    self.local_graph_store['current'] = self.local_graph_store['hm_sermons']

        except:
            msg = oErr.get_error_message()
            oErr.DoError("generate_graphs")

        # save figures in a dictionary for sending to the dcc.Store
        return self.local_graph_store, msg


