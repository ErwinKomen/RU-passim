import pandas as pd
import plotly.graph_objs as go
import pandas as pd
import os
import json
from collections.abc import Mapping
import re


current_dir = os.path.realpath(os.path.dirname(__file__))



# Define the sorting key function
def sort_key(s):
    pattern = re.compile('.*(\d{1,3}?).*')
    match = pattern.search(s)
    return (int(match.group(1)))

def plotly_heatmap( distances:pd.DataFrame, title:str = "", save_as:str=None, hoverinfo=None, text=None ):
    fig = go.Figure()
    fig.update_layout(width=800, height=800)

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
    return fig


## following is only needed to not reload data each time in dashboard, but also not to mess with dict of dicts of dicts :)

current_dir      =  os.path.realpath(os.path.dirname(__file__))
# For testing
current_dir = os.path.realpath("d:/etc/passim-plugin/preprocessed_data")
preproc_data_dir =  os.path.abspath(os.path.join(current_dir, "../preprocessed_data"))

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
        return pd.read_csv(os.path.join(self.folder, name + '.csv')).set_index(self.index)

    def __iter__(self):
        return iter(self._raw_dict)

    def __len__(self):
        return len(self._raw_dict)

    def keys(self):
        return self._keys


class series_data:
    def __init__(self, name=None):
        if name is not None:
            self.id                 = name
            self.main_dir           = os.path.join(preproc_data_dir, name)
            
            self.char_dist_dir      = os.path.join(self.main_dir, "char_distances")
            self.char_dist_names    = [ name.split('.')[0] for name in os.listdir(self.char_dist_dir) ] + ['Uniform']
            self.char_distances     = LazyLoader(self.char_dist_dir, self.char_dist_names, 'text_id')
            
            
            self.serie_distances    = {}
            self.serie_dist_names   = {}
            for serm_distance in self.char_dist_names:
                # print(serm_distance, serie_dist_dir)
                serie_dist_dir      = os.path.join(self.main_dir, f"distances/{serm_distance}")
                self.serie_dist_names[serm_distance]    = [ name.split('.')[0] for name in os.listdir(serie_dist_dir) ]
                self.serie_distances[serm_distance]     = LazyLoader(serie_dist_dir, self.serie_dist_names[serm_distance], 'SeriesName')
            # self.serie_distances  = LazyDict({ name.split('.')[0]:  for name in os.listdir(self.serie_dist_dir) })
            
            self.char_codes         = pd.read_csv(os.path.join(self.main_dir, 'char_codes.csv')).set_index("SermonName")
            # print(self.char_codes)

            self.char_series        = pd.read_csv(os.path.join(self.main_dir, 'char_series.csv')).set_index("SeriesName")
            try:
                self.metadata       = pd.read_csv(os.path.join(self.main_dir, 'metadata.csv')).set_index("SeriesName")
                def extract_age(date, by_first=True):
                    if not str(date).split("-")[0].isnumeric():
                        return float('nan')
                    else:
                        return float(int(str(date).split("-")[0]) // 100)
                self.metadata["age"]   = self.metadata.date.apply( extract_age )
            except:
                try:
                    self.metadata       = pd.read_csv(os.path.join(self.main_dir, 'metadata.csv')).set_index("SeriesName")
                except:
                    self.metadata       = pd.DataFrame(index=self.char_series.index)




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
    # def to_json(self):
    #     return json.dumps({
    #     "id"                : self.id,
    #     "main_dir"          : self.main_dir,
    #     "char_dist_dir"     : self.char_dist_dir,
    #     "serie_dist_dir"    : self.char_dist_dir,
    #     "char_distances"    : {name : self.char_distances[name].to_dict() for name in self.char_distances},
    #     "serie_distances"   : {name : self.serie_distances[name].to_dict() for name in self.serie_distances}
    # })

    # @staticmethod
    # def from_json(data):
    #     dict_data = json.loads(data)
    #     return series_data(dict_data)





#if __name__ == '__main__':
#    data = series_data(os.listdir(preproc_data_dir)[1])
#    print(data)
#    print(data.get_umap_hovertext())



