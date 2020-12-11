
from django.apps import apps
from django.contrib import admin
from django.contrib.auth import login, authenticate
from django.contrib.auth.models import Group, User
from django.core.urlresolvers import reverse
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
import openpyxl
from openpyxl.utils.cell import get_column_letter
from openpyxl.cell import Cell
from openpyxl import Workbook
from io import StringIO

# ======= imports from my own application ======
from passim.settings import APP_PREFIX, MEDIA_DIR
from passim.utils import ErrHandle

from passim.seeker.models import Manuscript, SermonDescr
from passim.reader.views import ReaderImport
from passim.reader.forms import UploadFileForm



class ManuscriptUploadExcel(ReaderImport):
    """Specific parameters for importing ECODEX"""

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
                        oResult = None

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
                                    k = ws_manu.cell(row=row_num, column=1).value.lower()
                                    v = ws_manu.cell(row=row_num, column=2).value
                                    if k == "":
                                        bStop = True
                                    else:
                                        row_num += 1
                                        oManu[k] = v
                                # We have an object with key/value pairs: process it
                                manu = Manuscript.add_one(oManu)

                                # Check if there is a "Sermon" worksheet
                                if ws_sermo != None:
                                    # Process the sermons in this sheet
                                    pass


                        # Create a report and add it to what we return
                        oContents = {'headers': lHeader, 'list': lst_manual, 'read': lst_read}
                        oReport = Report.make(username, "iecod", json.dumps(oContents))
                                
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

