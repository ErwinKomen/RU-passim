
import os
import json

import plotly
import plotly.express as px
import plotly.graph_objs as go
import plotly.figure_factory as ff


import pandas as pd
# This is not used import seaborn as sns
from itertools import cycle
from umap.umap_ import UMAP





from passim.plugin.utils import plotly_heatmap
from passim.utils import ErrHandle


class GenGraph(object):
    local_graph_store = {}
    store = {}
    reset_length = False

    def __init__(self, dic_this=None, dic_store=None):
        self.local_graph_store = {}
        self.store = {}
        self.reset_length = False
        if not dic_this is None:
            self.set_local_graph(dic_this)
        if not dic_store is None:
            self.set_store(dic_store)

    def set_local_graph(self, dic_this):
        if not dic_this is None and isinstance(dic_this,dict):
            for k,v in dic_this.items():
                self.local_graph_store[k] = v

    def set_store(self, dic_this):
        if not dic_this is None and isinstance(dic_this,dict):
            for k,v in dic_this.items():
                self.store[k] = v

    def set_reset_length(self, bValue):
        self.reset_length = bValue

    def generate_graphs(self, arg_dic):
        """
        This callback generates three simple graphs from random data.
        """
        # OLD: global local_graph_store, store, reset_length

        oErr = ErrHandle()
        try:
            # Convert the dictionary to actual parameters
            active_tab = arg_dic.get("active_tab")
            dataset = arg_dic.get("dataset")
            serdist = arg_dic.get("serdist")
            sermdist = arg_dic.get("sermdist")
            method = arg_dic.get("method")
            min_length = arg_dic.get("min_length")
            umap_dim = arg_dic.get("umap_dim")
            umap_hl = arg_dic.get("umap_hl")
            contains = arg_dic.get("contains")
            anchor_ms = arg_dic.get("anchor_ms")
            nb_closest = arg_dic.get("nb_closest")
            umap_md = arg_dic.get("umap_md")
            umap_nb = arg_dic.get("umap_nb")

            if dataset is None:
                # generate empty graphs when app loads
                return self.local_graph_store, ""

    
            if serdist is not None:
                # todo: lazy loading

                # adding filtering by content (for now, mere presence of all the specified sermons)
                def all_sermons_present(content, desired_sermons):
                    keep = True
                    # print(content)
                    for serm in desired_sermons:
                        # print(store[dataset].char_codes.loc[serm])
                        if not self.store[dataset].char_codes.loc[serm]["Code"] in content:
                            keep = False
                            break
                    return keep

                long_serie = self.store[dataset].char_series['EncodedWorks'].apply(lambda x: len(x) >= min_length and all_sermons_present(x, contains) if contains and len(contains) > 0 else len(
                    x) >= min_length)
                dist_matrix = self.store[dataset].serie_distances[sermdist][serdist].loc[long_serie, long_serie]

                # if anchor manuscript is given, we need to update our dist_matrix
                if anchor_ms:
                    anchor_ms_idx = self.store[dataset].metadata[self.store[dataset].metadata["ms_identifier"] == anchor_ms].index.tolist()
                    # in length of anchor manuscript is less than minimal lenght of the series,
                    # setting minimal length to length of the anchor ms (see callback above)
                    try:
                        closest_mss_idx = dist_matrix[anchor_ms_idx[0]].sort_values(ascending=True).head(nb_closest).index.tolist()
                    except KeyError:
                        reset_length = True
                        anchor_ms_length = self.store[dataset].metadata.loc[anchor_ms_idx[0]]["total"]
                        long_serie = self.store[dataset].char_series['EncodedWorks'].apply(
                            lambda x: len(x) >= anchor_ms_length)
                        dist_matrix = self.store[dataset].serie_distances[sermdist][serdist].loc[long_serie, long_serie]
                        closest_mss_idx = dist_matrix[anchor_ms_idx[0]].sort_values(ascending=True).head(
                            nb_closest).index.tolist()

                    dist_matrix = dist_matrix.loc[closest_mss_idx, closest_mss_idx]

                if active_tab == 'hm_series':
                    hovertext = self.store[dataset].get_serie_hm_hovertext(dist_matrix)
                    self.local_graph_store['hm_series'] = plotly_heatmap(
                        dist_matrix,
                        hoverinfo='text',
                        text=hovertext
                        )
                if active_tab == 'clusters':

                    # creating labels for dendrogram
                    clustering_metadata = self.store[dataset].metadata[self.store[dataset].metadata.index.isin(dist_matrix.index)]
                    clustering_metadata["SeriesName"] = clustering_metadata.index
                    hovertext = self.store[dataset].get_clustering_hovertext(clustering_metadata)

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

                    if len(umap_hl) == 1 and umap_hl[0] in self.store[dataset].metadata.columns.tolist():
                        color_col = umap_hl[0]
                        cont_coloring = True
                        if self.store[dataset].metadata[color_col].dtype != 'float':
                            cont_coloring = False
                            colorize = {x:x for x in self.store[dataset].metadata[umap_hl[0]].unique().tolist()}
                    else:            
                        cont_coloring = False
                        color_col = "SeriesName"
                        # getting index from actual ms_identifiers
                        mask = (self.store[dataset].metadata["ms_identifier"].isin(umap_hl))
                        umap_hl = self.store[dataset].metadata.index[mask]

                        colorize = {x:x for x in umap_hl}

                    # go_colors = cycle(plotly.colors.sequential.Viridis)
                    go_colors = cycle(px.colors.qualitative.Dark24)

                    proj = umap_.fit_transform(dist_matrix)
                    proj_df = pd.DataFrame(proj) 

                    # print(store[dataset].metadata.shape)
                    proj_df["SeriesName"] = dist_matrix.index
                    proj_df = pd.concat( [ proj_df.set_index("SeriesName"), self.store[dataset].metadata], axis=1)
                    proj_df["SeriesName"] = proj_df.index

                    hovertext = self.store[dataset].get_umap_hovertext(proj_df)

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
    
            if active_tab == 'hm_sermons' and sermdist is not None and sermdist != "Uniform":
        
                dist_matrix =  self.store[dataset].char_distances[sermdist]
                rename      =  self.store[dataset].char_codes
                rename["SermonName"] = rename.index
                rename.set_index("Code", inplace=True)
                dist_matrix.rename(
                    columns= lambda x: rename["SermonName"].loc[x],
                    index  = lambda x: rename["SermonName"].loc[x],
                    inplace=True
                    )

                self.local_graph_store['hm_sermons'] = plotly_heatmap(dist_matrix)

        except:
            msg = oErr.get_error_message()
            oErr.DoError("generate_graphs")

        # save figures in a dictionary for sending to the dcc.Store
        return self.local_graph_store, ""


