""" Passim-tailored version of dashboard
"""

import re
from django.http import HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string
#import plotly.graph_objects as go

from passim.plugin.forms import BoardForm
from passim.utils import ErrHandle
from passim.basic.views import BasicPart
from passim.plugin.calculate import GenGraph
from passim.plugin.models import ClMethod, Highlight


def sermonboard(request):
    """Renders the Sermon Board templat."""

    prefix = 'brd'
    # Specify the template
    template_name = 'plugin/sermonboard.html'
    boardForm = None
    context = {}
    response = HttpResponse("empty sermonboard")
    oErr = ErrHandle()
    try:
        # Check if Highlight needs loading
        Highlight.initialize()

        # Figure out what the proper context should be
        boardForm = BoardForm(prefix=prefix)
        context = dict(title="SermonBoard", boardForm=boardForm)

        # Calculate the response as a string
        response = render_to_string( template_name, context, request)

        # Repair the django_select2 css type
        response = response.replace('django_select2/django_select2.css"', 'django_select2/django_select2.css" type="text/css"')
        # Calculate the HTTP response
        response = HttpResponse(response)
    except:
        msg = oErr.get_error_message()
        oErr.DoError("sermonboard")
    # Return the correct response
    return response


class BoardApply(BasicPart):
    """When the user hits the 'Apply' button, this is where we need to process it"""

    prefix = 'brd'
    form_objects = [{'form': BoardForm, 'prefix': prefix, 'readonly': True}]
    template_name = None

    empty_graph_data = {} # {k: None for k in ["hm_series", "hm_sermons", "umap", "clusters"]}
    store = {}

    def add_to_context(self, context):
        """Do what we need to do, and then return the adapted context"""
        
        oErr = ErrHandle()
        try:
            # Process the information from [brdForm]
            brdForm = context['brdForm']
            cleaned_data = self.form_objects[0]['cleaned_data']
            # Get the data from cleaned_data
            if not cleaned_data is None:
                dataset = cleaned_data.get("dataset")       # [1] obligatory
                sermdist = cleaned_data.get("sermdist")     # [1] obligatory
                serdist = cleaned_data.get("serdist")       # [1] obligatory
                sermons = cleaned_data.get("sermons")
                anchorman = cleaned_data.get("anchorman")
                umap_dim = cleaned_data.get("umap_dim")     # [1] obligatory
                cl_method = cleaned_data.get("cl_method")
                highlights = cleaned_data.get("highlights")

                if cl_method is None:
                    cl_method = ClMethod.objects.filter(code="ward").first()

                # Slider values that are not part of BoardForm strictly speaking
                nb_closest = self.qd.get("brd-nb_closest")
                min_length = self.qd.get("brd-min_length")
                umap_md = self.qd.get("brd-umap_md")
                umap_nb = self.qd.get("brd-umap_nb")

                # Convert the integers and floats where possible
                nb_closest = int(nb_closest)
                min_length = int(min_length)
                umap_md = float(umap_md)
                umap_nb = int(umap_nb)

                # Pick up what the active tab is 
                active_tab = self.qd.get("brd-active_tab")
                if active_tab is None:
                    active_tab = "umap"
                else:
                    active_tab = active_tab.replace("tab-", "")

                # Validate the input
                ar_err = []
                # One dataset should have been specified
                if dataset is None:
                    # A dataset should have been specified
                    ar_err.append("Specify a dataset")
                if sermdist is None:
                    ar_err.append("Specify sermons distance")
                if serdist is None:
                    ar_err.append("Specify series distance")

                msg = "\n".join(ar_err)
                # Can we continue?
                if msg == "":
                    # Yes, we can continue

                    # (1) Initialize local_graph_store
                    hm_series = None
                    hm_sermons = None
                    umap = None
                    data = None
                    dict_lgs = dict(hm_series=hm_series, hm_sermons=hm_sermons,
                                    umap=umap, data=data)
                    dict_tab = dict(ser_hm="hm_series", clustering="clusters", serm_hm="hm_sermons", umap="umap")
                    # (2) Initialize store
                    dict_st = None # dict(passim_core_custom=None)
                    # (3) Create a GenGraph object
                    gengraph = GenGraph(dict_lgs, dict_st)
                    # (4) Call the object with appropriate values for its arguments
                    arg_dic = {}
                    arg_dic['active_tab'] = dict_tab[active_tab]
                    arg_dic['dataset'] = dataset.location
                    arg_dic['serdist'] = serdist.codepath
                    arg_dic['sermdist'] = sermdist.codepath
                    arg_dic['method'] = cl_method.abbr
                    arg_dic['umap_dim'] = umap_dim.name
                    arg_dic['umap_hl'] = [x.name for x in highlights]
                    arg_dic['contains'] = [x.name for x in sermons]
                    arg_dic['anchor_ms'] = None if anchorman is None else anchorman.get_name()
                    arg_dic['nb_closest'] = nb_closest
                    arg_dic['umap_md'] = umap_md
                    arg_dic['umap_nb'] = umap_nb
                    arg_dic['min_length'] = min_length

                    # Generate the Plotly graph
                    dict_of_fig, msg = gengraph.generate_graphs(arg_dic)

                    # Check if all is okay
                    if msg == "" and "current" in dict_of_fig:
                        # Figure out which one to show
                        
                        # All is well, now show the figure
                        fig = dict_of_fig.get("current")
                        if fig is None or isinstance(fig,str):
                            errMsg = "BoardApply generate_graphs did not produce figure <code>{}</code>".format(arg_dic['active_tab'])
                            oErr.Status(errMsg)
                            self.arErr.append(errMsg)
                            context['data'] = dict(msg=errMsg)
                        else:
                            fig.update_layout(showlegend=True)
                            html_code = fig.to_html(full_html=False)
                            context['data'] = dict(html=html_code)
                    else:
                        errMsg = "<code>BoardApply cannot generate figure:</code><br /><code>{}</code>".format(msg)
                        oErr.Status(errMsg)
                        self.arErr.append(errMsg)
                        context['data'] = dict(msg=errMsg)
                else:
                    # There is an error message: return that
                    context['data'] = dict(msg=msg)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("BoardApply/add_to_context")

        # Return the emended context
        return context
