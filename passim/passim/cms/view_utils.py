"""
Definition of views for the CMS app.
"""

from passim.utils import ErrHandle
from passim.cms.models import Citem, Cpage, Clocation


def cms(page, idc, message, label=None):
    """Render the [message] as it is, or as the user has provided it
    
    If there is no entry for this message yet, then create one
    """

    oErr = ErrHandle()
    try:
        # Locate this Citem
        obj = Citem.objects.filter(clocation__page__urlname__iexact=page, clocation__htmlid=idc).first()
        if obj is None:
            cpage = Cpage.objects.filter(urlname__iexact=page).first()
            if cpage is None:
                cpage = Cpage.objects.create(urlname=page, name=page)
            # Do we have an idc?
            if idc is None:
                # There is no idc: use the label
                clocation = Clocation.objects.filter(page=cpage, name__iexact=label).first()
                if clocation is None:
                    clocation = Clocation.objects.create(page=cpage, name=label)
            else:
                # There is an idc: use that as point of search
                clocation = Clocation.objects.filter(page=cpage, htmlid=idc).first()
                if clocation is None:
                    if label is None:
                        clocation = Clocation.objects.create(page=cpage, htmlid=idc)
                    else:
                        clocation = Clocation.objects.create(page=cpage, htmlid=idc, name=label)
            # Need to add this message to the current value
            obj = Citem.objects.create(clocation=clocation, contents=message, original=message)
        message = obj.contents
    except:
        msg = oErr.get_error_message()
        oErr.DoError("cms")
    return message

def cms_translate(page, mainitems):
    """Provide alternative 'title' messages for the mainitems"""

    oErr = ErrHandle()
    try:
        if not mainitems is None and not page is None and len(mainitems) > 0 and page != "":
            for oItem in mainitems:
                # Check if it has a title
                title = oItem.get("title")
                # Note: if there is no 'title' defined by default, then NONE will result
                # if not title is None:
                # Get the key and get the label
                label = oItem.get("label")
                fname = oItem.get("field_key")
                if fname is None:
                    fname = oItem.get("field_list")
                    if fname is None:
                        fname = label.lower()
                # Get or add this
                newtitle = cms(page, fname, title, label=label)
                # Replace if needed
                if newtitle != title:
                    oItem['title'] = newtitle

    except:
        msg = oErr.get_error_message()
        oErr.DoError("cms_translate")
    return mainitems

