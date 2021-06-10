
from django.apps import apps
from django.contrib import admin
from django.contrib.auth import login, authenticate
from django.contrib.auth.models import Group, User
from django.urls import reverse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import transaction
from django.db.models import Q, Prefetch, Count, F
from django.db.models.functions import Lower
from django.db.models.query import QuerySet 
from django.forms import formset_factory, modelformset_factory, inlineformset_factory, ValidationError
from django.forms.models import model_to_dict
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, JsonResponse, FileResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.template.loader import render_to_string
from django.template import Context
from django.views.generic.detail import DetailView
from django.views.generic.base import RedirectView
from django.views.generic import ListView, View
from django.views.decorators.csrf import csrf_exempt

# General imports
import io, sys, os
import openpyxl, json
from openpyxl.utils.cell import get_column_letter
from openpyxl.cell import Cell
from openpyxl import Workbook
from io import StringIO

# ======= imports from my own application ======
from passim.settings import APP_PREFIX, MEDIA_DIR
from passim.utils import ErrHandle

from passim.seeker.models import Manuscript, SermonDescr, Profile, Report
from passim.seeker.views import app_editor
from passim.reader.views import ReaderImport
from passim.reader.forms import UploadFileForm



class ManuscriptUploadExcel(ReaderImport):
    """Specific parameters for importing manuscripts from Excel"""

    import_type = "excel"
    sourceinfo_url = "https://www.ru.nl/english/people/boodts-s/"

    def process_files(self, request, source, lResults, lHeader):
        file_list = []
        oErr = ErrHandle()
        bOkay = True
        code = ""
        oStatus = self.oStatus
        try:
            # Make sure we have the username
            username = self.username
            profile = Profile.get_user_profile(username)
            team_group = app_editor
            kwargs = {'profile': profile, 'username': username, 'team_group': team_group}

            # Get the contents of the imported file
            files = request.FILES.getlist('files_field')
            if files != None:
                for data_file in files:
                    filename = data_file.name
                    file_list.append(filename)

                    # Set the status
                    oStatus.set("reading", msg="file={}".format(filename))

                    # Get the source file
                    if data_file == None or data_file == "":
                        self.arErr.append("No source file specified for the selected project")
                    else:
                        # Check the extension
                        arFile = filename.split(".")
                        extension = arFile[len(arFile)-1]

                        lst_manual = []
                        lst_read = []

                        # Further processing depends on the extension
                        oResult = {'status': 'ok', 'count': 0, 'sermons': 0, 'msg': "", 'user': username}

                        if extension == "xlsx":
                            # This is an Excel file: read the file using openpyxl
                            # Write data temporarily to the WRITABLE dir, but with a temporary filename
                            tmp_path = os.path.abspath(os.path.join( MEDIA_DIR, filename))
                            with io.open(tmp_path, "wb") as f:
                                sData = data_file.read()
                                f.write(sData)

                            # Read string file
                            wb = openpyxl.load_workbook(tmp_path, read_only=True)
                            sheetnames = wb.sheetnames
                            ws_manu = None
                            ws_sermo = None
                            for sname in sheetnames:
                                if "manu" in sname.lower():
                                    ws_manu = wb[sname]
                                elif "sermo" in sname.lower():
                                    ws_sermo = wb[sname]
                            # Do we have a manuscript worksheet?
                            if ws_manu != None:
                                # Process the manuscript-proper details: columns Name and Value
                                oManu = {}
                                row_num = 1
                                if ws_manu.cell(row=row_num, column=1).value.lower() == "field" and \
                                   ws_manu.cell(row=row_num, column=2).value.lower() == "value":
                                    # we can skip the first row
                                    row_num += 1
                                bStop = False
                                while not bStop:
                                    k = ws_manu.cell(row=row_num, column=1).value
                                    v = ws_manu.cell(row=row_num, column=2).value
                                    if k == "" or k == None:
                                        bStop = True
                                    else:
                                        row_num += 1
                                        k = k.lower()
                                        oManu[k] = v
                                # We have an object with key/value pairs: process it
                                manu = Manuscript.custom_add(oManu, **kwargs)

                                oResult['count'] += 1
                                oResult['obj'] = manu
                                oResult['name'] = manu.idno

                                # Check if there is a "Sermon" worksheet
                                if ws_sermo != None:
                                    # Get the column names
                                    row_num = 1
                                    column = 1
                                    header = []
                                    v = ws_sermo.cell(row=row_num, column=column).value
                                    while v != None and v != "" and v != "-":                                        
                                        header.append(v.lower())
                                        column += 1
                                        v = ws_sermo.cell(row=row_num, column=column).value
                                    # Process the sermons in this sheet
                                    sermon_list = []
                                    column = 1
                                    row_num += 1
                                    v = ws_sermo.cell(row=row_num, column=column).value
                                    while v != "" and v != None:
                                        # ==== DEBUG ====
                                        oErr.Status("Upload excel row_num={}".format(row_num))
                                        # ===============

                                        # Create a new sermon object
                                        oSermon = {}
                                        # Process this row
                                        for idx, col_name in enumerate(header):
                                            column = idx + 1
                                            oSermon[col_name] = ws_sermo.cell(row=row_num, column=column).value
                                        # Process this sermon
                                        order = oSermon['order']
                                        sermon = SermonDescr.custom_add(oSermon, manu, order)

                                        oResult['sermons'] += 1

                                        # Get parent, firstchild, next
                                        parent = oSermon['parent']
                                        firstchild = oSermon['firstchild']
                                        nextone = oSermon['next']
                                        # Add to list
                                        sermon_list.append({'order': order, 'parent': parent, 'firstchild': firstchild,
                                                            'next': nextone, 'sermon': sermon})
                                        # GO to the next row for the next sermon
                                        row_num += 1
                                        column = 1
                                        v = ws_sermo.cell(row=row_num, column=column).value

                                    # Now process the parent/firstchild/next items
                                    with transaction.atomic():
                                        for oSermo in sermon_list:
                                            # Get the p/f/n numbers
                                            parent_id = oSermo['parent']
                                            firstchild_id = oSermo['firstchild']
                                            next_id = oSermo['next']
                                            # Process parent
                                            if parent_id != '' and parent_id != None:
                                                # parent_id = str(parent_id)
                                                parent = next((obj['sermon'] for obj in sermon_list if obj['order'] == parent_id), None)
                                                oSermo['sermon'].msitem.parent = parent.msitem
                                                oSermo['sermon'].msitem.save()
                                            # Process firstchild
                                            if firstchild_id != '' and firstchild_id != None:
                                                # firstchild_id = str(firstchild_id)
                                                firstchild = next((obj['sermon'] for obj in sermon_list if obj['order'] == firstchild_id), None)
                                                oSermo['sermon'].msitem.firstchild = firstchild.msitem
                                                oSermo['sermon'].msitem.save()
                                            # Process next
                                            if next_id != '' and next_id != None:
                                                # next_id = str(next_id)
                                                nextone = next((obj['sermon'] for obj in sermon_list if obj['order'] == next_id), None)
                                                oSermo['sermon'].msitem.next = nextone.msitem
                                                oSermo['sermon'].msitem.save()


                        # Create a report and add it to what we return
                        oContents = {'headers': lHeader, 'list': lst_manual, 'read': lst_read}
                        oReport = Report.make(username, "ixlsx", json.dumps(oContents))
                                
                        # Determine a status code
                        statuscode = "error" if oResult == None or oResult['status'] == "error" else "completed"
                        if oResult == None:
                            self.arErr.append("There was an error. No manuscripts have been added")
                        else:
                            lResults.append(oResult)
            code = "Imported using the [import_excel] function on this filew: {}".format(", ".join(file_list))
        except:
            bOkay = False
            code = oErr.get_error_message()
        return bOkay, code


class ManuscriptUploadJson(ReaderImport):
    pass

