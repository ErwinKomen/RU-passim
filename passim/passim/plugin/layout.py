import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
import os
from utils import series_data

app = dash.Dash(external_stylesheets=[dbc.themes.LUX])
current_dir = os.path.realpath(os.path.dirname(__file__))
empty_graph_data = {k: None for k in ["hm_series", "hm_sermons", "umap", "clusters"]}
store = {}

# top-line droppouts with choosing dataset, series dist type and so on
header_droppouts = dbc.Row([
    dbc.Col([
        html.H4("Dataset"),
        dcc.Dropdown(
           [
            x for x in os.listdir(os.path.join(current_dir, "../preprocessed_data")) 
            if os.path.isdir(os.path.join(current_dir, f"../preprocessed_data/{x}/"))
           ],
           id='dataset',
            value="passim_core_custom"
           ),
        ]),

    dbc.Col([
            html.H4("Sermons distance"),
            dcc.Dropdown(
                ['LDA Euclidean', 'LDA cosine', 'Constant', 'Freq'],
                id='sermons-distance'
            ),                        
        ],
        style= {'display': 'block'},
        id="sermons-distance-col"),
    dbc.Col([
        html.H4("Series distance"),
        dcc.Dropdown(
           ['Edit', 'LCS', 'Frequency analys'],
           id='series-distance',
            value="Edit"
           ),
        ],
        style= {'display': 'block'},
        id="series-distance-col"
        ),

    dbc.Col([
            # html.H4("       "),
            html.Div([
                dbc.Button(
                    [
                    dbc.Spinner(
                        children=html.Div(id="recomputing"),
                        size="sm"), 
                    " Recompute"],
                    id='recompute-btn',
                    color="primary",
                    disabled=True,
                ),
            ]
        )
    ])
])


# left column with current tab parameters
controls = dbc.Card(

    [
# adding whole new section to filter content by:
#- List of sermons contained in the manuscript
#- Length of the manuscript
#- "Anchor" manuscript + num closest, according to the selected metric
        html.Div(
            [
                html.H5("Content filter"),
                # dbc.Label("Content filter"),
                html.Div(id='min-length-output-container'),
                dcc.Slider(
                    min=1, 
                    max=100,
                    marks=None, 
                    value=5,
                    step=1,
                    id='min-length'),
                dbc.Label("Sermons"),

                dcc.Dropdown(
                    id="contains",
                    options=['AU s 202', "AU s 46", "AU s 355"],
                    value=None,
                    multi=True
                ),

                dbc.Label("Anchor manuscript"),
                dcc.Dropdown(
                    id="anchor-ms",
                    options=["France, Avranches, Bibliothèque municipale, 94"],
                    value=None,
                    multi=False
                ),
                html.Div(
                    id='nb-closest-container'
                         ),
                dcc.Slider(
                    min=1,
                    step=1,
                    max=200,
                    marks=None,
                    value=10,
                    id='nb-closest',
                ),
            ],
            id='filtering-container'
        ),
        html.Div(
            [ 
                dbc.Label("Clustering method"),
                dcc.Dropdown(
                    id="cl-method",
                    options=['single', 'complete','average', 'centroid',  'median', 'ward'],
                    value="ward",
                ),
            ],
            style= {'display': 'none'},
            id="clustering_params"
        ),

        html.Div(
            [ 
                dbc.Label("Target dimension"),
                dcc.Dropdown(
                    id="umap-dim",
                    options=['2D', '3D'],
                    value="2D",
                ),
                dbc.Label("Highlight"),
                dcc.Dropdown(
                    id="umap-hl",
                    options=['ms_32', "ms_1404", "ms_3104", "other"],
                    value=['century'],
                    multi=True
                ),
                html.Div(id='nb-output-container'),
                dcc.Slider(
                    min=1, 
                    step=1,
                    max=200,
                    marks=None, 
                    value=10,
                    id='umap-nb'),

                html.Div(id='md-output-container'),
                dcc.Slider(
                    min=0, 
                    max=1,
                    step=0.01,
                    value=0.1,
                    marks=None, 
                    id='umap-md'
                ),

            ],
            style= {'display': 'none'},
            id="umap_params"
        ),
        html.Div(
            [
                dbc.Button(
                    "Apply",
                    color="primary",
                    id="apply-button",
                    # className="mb-3",
                    style={'margin-right': '10px'},
                ),

                dbc.Button(
                    "Reset",
                    color="primary",
                    id="reset-button",
                    # className="mb-3",
                )
            ],
            id='buttons-container'
        ),
    ],
    body=True,
)

# tabs & loading
tabs = dbc.Row([
                dbc.Col(controls),
                dbc.Col([
                    dbc.Tabs(
                    [
                        dbc.Tab(label="Clustering", tab_id="clusters"),
                        dbc.Tab(label="Umap", tab_id="umap"),
                        dbc.Tab(label="Series Heatmap", tab_id="hm_series"),
                        dbc.Tab(label="Sermons Heatmap", tab_id="hm_sermons"),
                    ],
                    id="tabs",
                    active_tab="umap",
                    ),
                    dbc.Spinner(
                        id="spinner", 
                        spinner_style={"width": "3rem", "height": "3rem"},
                        children=html.Div(id="loading",className='p-4')
                        ),
                    html.Div(id="tab-content", className="p-4"),
                    ],
                    md=8
                )
                
        ])

app.layout = dbc.Container(
    [
        dcc.Store(id="store"),
html.Div([

    # adding this to catch exception when the length of the anchor ms is in conflict with min-length (see dashboard.py)
    dcc.Interval(
        id='interval-component',
        interval=1*1000,
        n_intervals=0
    ),
    dcc.Store(id='reset-length-store'),
]),
        html.H1("Sermon Collections"),
        html.Hr(),
        html.Div([
            dbc.Row(header_droppouts)
            ]),
                 
        html.Hr(),
        html.Div(
            dbc.Row(tabs)
    
        )
        ])

## callbacks for showin' what's selected in sliders
@app.callback(
    Output('nb-output-container', 'children'),
    Input('umap-nb', 'value')
)
def update_nb_text(umap_nb):
    return f'Number of neighbours                   {umap_nb}'

@app.callback(
    Output('nb-closest-container', 'children'),
    Input('nb-closest', 'value')
)
def update_nb_closest_text(nb_closest):
    return f'Number of closest manuscripts                   {nb_closest}'

@app.callback(
    Output('md-output-container', 'children'),
    Input('umap-md', 'value')
)
def update_nb_text(umap_md):
    return f'Minimal distance                       {umap_md}'

@app.callback(
    Output('min-length-output-container', 'children'),
    Input('min-length', 'value')
)
def update_ml_text(min_length):
    return f'Minimal Collection Length                   {min_length}'

# only available data can be choosen:
@app.callback(
   Output(component_id='sermons-distance-col', component_property='style'),
   Output(component_id='sermons-distance', component_property='options'),
   Output(component_id='sermons-distance', component_property='value'),
   Input(component_id="dataset", component_property="value"),
   )
def sermons_dist_dropdown(dataset):
    if dataset is None:
        return {'display': 'none'}, [],"Uniform"
    global store
    store[dataset] = series_data(dataset)
    names = store[dataset].char_dist_names
    if len(names) > 1:
        return {'display': 'block'}, names, "Uniform"
    else:
        return {'display': 'none'}, [], 'Uniform'


@app.callback(
   Output(component_id='series-distance-col', component_property='style'),
   Output(component_id='series-distance', component_property='options'),
   Output(component_id='series-distance', component_property='value'),
   Input(component_id="dataset", component_property="value"),
   Input(component_id='sermons-distance', component_property='value'),


   )
def series_dist_dropdown(dataset, sermdist):
    if dataset is None:
        return {'display': 'none'}, []
    global store
    store[dataset] = series_data(dataset)
    names = sorted(store[dataset].serie_dist_names[sermdist])
    if len(names) > 0:
        return {'display': 'block'}, names, names[0]
    else:
        return {'display': 'none'}, [], None


# callbacks for showing only actual filtering params 
@app.callback(
   Output(component_id='clustering_params', component_property='style'),
   [Input("tabs", "active_tab")])
def render_filter_tab(active_tab):
    if active_tab == 'clusters':
        return {'display': 'block'}
    else:
        return {'display': 'none'}

@app.callback(
   Output(component_id='umap_params', component_property='style'),
   [Input("tabs", "active_tab")])
def render_filter_tab(active_tab):
    if active_tab == 'umap':
        return {'display': 'block'}
    else:
        return {'display': 'none'}




# render tab data
@app.callback(
    Output("tab-content", "children"),
    Output("loading", "children", allow_duplicate=True),
    [Input("tabs", "active_tab"), 
    Input("store", "data"), ],
    prevent_initial_call=True,
)
def render_tab_content(active_tab, data):
    """
    This callback takes the 'active_tab' property as input, as well as the
    stored graphs, and renders the tab content depending on what the value of
    'active_tab' is.
    """
    # adding custumized download options The default behaviour is to download a PNG of size 700 by 450 pixels.
    config = {
        'toImageButtonOptions': {
            'format': 'svg',  # one of png, svg, jpeg, webp
            'filename': f'{active_tab}_chart',
            'height': 1000,
            'width': 1000,
            'scale': 3  # Multiply title/legend/axis/canvas sizes by this factor
        }
    }

    if active_tab is None:
        return "No tab selected", ""
    if data is None:
        return "No data privided", ""
 
    if active_tab == "hm_series":
        if data["hm_series"] is not None:
            return dcc.Graph(figure=data["hm_series"]), ""
        else:
            return "Specify series distance", ""
    elif active_tab == "hm_sermons":
        if data["hm_sermons"] is not None:
            return dcc.Graph(figure = data["hm_sermons"]), ""
        else:
            return "Specify sermons distance", ""
    elif active_tab == "clusters":
        if data["clusters"] is not None:
            return dcc.Graph(figure = data["clusters"], config=config), ""
        else:
            return "Specify clustring method and series distance", ""
    elif active_tab == "umap":
        if data["umap"] is not None:
            return dcc.Graph(figure = data["umap"], config=config), ""
        else:
            return "Specify series distance", ""

        
    return "No tab selected", ""


# stoprage update on dataset
# @app.callback(
#     Output(component_id='store', component_property='data'),
#     Input(component_id="dataset", component_property="value"),
#     State(component_id='store', component_property='data'),
#     prevent_initial_call=True,
# )
# def update_storaged_datasets(dataset, store):
#     if store is None:
#         store = empty_data
#     store[dataset] = series_data(dataset)
#     print("kek")
#     return store.__dict__()



if __name__ == '__main__':
    app.run_server(debug=True)