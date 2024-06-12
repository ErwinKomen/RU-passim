"""
Definition of urls for passim.
"""

from datetime import datetime
from django.contrib.auth.decorators import login_required, permission_required
# from django.conf.urls import include #, url # , handler404, handler400, handler403, handler500
from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from django.http import HttpResponseNotFound
from django.urls import path, re_path
# from django.conf.urls import include
from django.urls.conf import include
import django.contrib.auth.views
import django

import passim.seeker.forms
import passim.seeker.views
import passim.reader.views
from passim import views
from passim.seeker.views import *
from passim.seeker.visualizations import *
from passim.dct.views import *
from passim.stemma.views import *
from passim.reader.views import *
from passim.enrich.views import *
from passim.cms.views import *
from passim.reader.excel import ManuscriptUploadExcel, ManuscriptUploadJson, ManuscriptUploadGalway, LibraryUploadExcel, \
    SermonGoldUploadJson, EqualGoldUploadEdilit
from passim.approve.views import EqualChangeDetails, EqualChangeEdit, EqualChangeUserEdit, EqualChangeUserDetails, \
    EqualApprovalDetails, EqualApprovalEdit, EqualApprovalUserDetails, EqualApprovalUserEdit, \
    EqualChangeList, EqualChangeUlist, EqualApprovalList, EqualApprovalUlist, EqualAddList, EqualAddUList, \
    EqualAddDetails, EqualAddEdit, EqualAddUserDetails, EqualAddUserEdit, EqualAddApprovalList, EqualAddApprovalUList,\
    EqualAddApprovalDetails, EqualAddApprovalEdit, EqualAddApprovalUserDetails, EqualAddApprovalUserEdit 
from passim.plugin.views import sermonboard, BoardApply
# Import from PASSIM as a whole
from passim.settings import APP_PREFIX

# Other Django stuff
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.base import RedirectView
from django.views.generic import TemplateView

# ================== Load plotly apps - this triggers their registration =======================
USE_DASH = False
try:
    import passim.plugin.simple
    import passim.plugin.dashboard
    USE_DASH = False
except:
    print("Not loading plugin simple and dashboard")
# ==============================================================================================

admin.autodiscover()

handler404 = 'passim.seeker.views.view_404'



# Set admin stie information
admin.site.site_header = "Patristic Sermons in the Middle Ages"
admin.site.site_title = "passim Admin"

pfx = APP_PREFIX
use_testapp = False

# ================ Custom error handling when debugging =============
def custom_page_not_found(request, exception=None):
    return passim.seeker.views.view_404(request)

handler404 = custom_page_not_found

urlpatterns = [
    # Examples:
    re_path(r'^$', passim.seeker.views.home, name='home'),
    #path("404/", custom_page_not_found),
    re_path(r'^favicon\.ico$',RedirectView.as_view(url='/static/seeker/content/favicon.ico')),
    re_path(r'^contact$', passim.seeker.views.contact, name='contact'),
    re_path(r'^about', passim.seeker.views.about, name='about'),
    re_path(r'^short', passim.seeker.views.about, name='short'),
    re_path(r'^guide', passim.seeker.views.guide, name='guide'),
    # re_path(r'^mypassim$', passim.dct.views.mypassim, name='mypassim'),
    re_path(r'^technical', passim.seeker.views.technical, name='technical'),
    re_path(r'^bibliography', passim.seeker.views.bibliography, name='bibliography'),
    re_path(r'^nlogin', passim.seeker.views.nlogin, name='nlogin'),

    re_path(r'^sync/passim/$', passim.seeker.views.sync_passim, name='sync_passim'),
    re_path(r'^sync/start/$', passim.seeker.views.sync_start, name='sync_start'),
    re_path(r'^sync/progress/$', passim.seeker.views.sync_progress, name='sync_progress'),
    re_path(r'^sync/zotero/$', passim.seeker.views.redo_zotero, name='sync_zotero'),

    re_path(r'^tools/clavis/$', passim.seeker.views.do_clavis, name='do_clavis'),
    re_path(r'^tools/goldtogold/$', passim.seeker.views.do_goldtogold, name='do_goldtogold'),
    re_path(r'^tools/goldsearch/$', passim.seeker.views.do_goldsearch, name='do_goldsearch'),
    re_path(r'^tools/stype/$', passim.seeker.views.do_stype, name='do_stype'),
    re_path(r'^tools/locations/$', passim.seeker.views.do_locations, name='do_locations'),
    re_path(r'^tools/provenance/$', passim.seeker.views.do_provenance, name='do_provenance'),
    re_path(r'^tools/mext/$', passim.seeker.views.do_mext, name='do_mext'),
    re_path(r'^tools/sermons/$', passim.seeker.views.do_sermons, name='do_sermons'),
    re_path(r'^tools/ssg/$', passim.seeker.views.do_ssgmigrate, name='do_ssgmigrate'),
    re_path(r'^tools/huwa/$', passim.seeker.views.do_huwa, name='do_huwa'),
    re_path(r'^tools/sermones/reset$', passim.dct.views.sermones_reset, name='sermones_reset'),

    re_path(r'^search/sermon', SermonListView.as_view(), name='search_sermon'),
    re_path(r'^search/manuscript', ManuscriptListView.as_view(), name='search_manuscript'),
    re_path(r'^search/collection',  CollectionListView.as_view(prefix="any"), name='search_collection'),
    re_path(r'^search/library', LibraryListView.as_view(), name='library_search'),
    re_path(r'^search/author', AuthorListView.as_view(), name='author_search'),

    re_path(r'^manuscript/list', ManuscriptListView.as_view(), name='manuscript_list'),
    re_path(r'^manuscript/details(?:/(?P<pk>\d+))?/$', ManuscriptDetails.as_view(), name='manuscript_details'),
    re_path(r'^manuscript/edit(?:/(?P<pk>\d+))?/$', ManuscriptEdit.as_view(), name='manuscript_edit'),
    re_path(r'^manuscript/ukw(?:/(?P<pk>\d+))?/$', ManuscriptUserKeyword.as_view(), name='manuscript_ukw'),
    re_path(r'^manuscript/hierarchy(?:/(?P<pk>\d+))?/$', ManuscriptHierarchy.as_view(), name='manuscript_hierarchy'),
    re_path(r'^manuscript/download(?:/(?P<pk>\d+))?/$', ManuscriptDownload.as_view(), name='manuscript_download'),
    re_path(r'^manuscript/import/excel/$', ManuscriptUploadExcel.as_view(), name='manuscript_upload_excel'),
    re_path(r'^manuscript/import/json/$', ManuscriptUploadJson.as_view(), name='manuscript_upload_json'),
    re_path(r'^manuscript/import/galway/$', ManuscriptUploadGalway.as_view(), name='manuscript_upload_galway'),
    re_path(r'^manuscript/codico/$', ManuscriptCodico.as_view(), name='manuscript_codico'),
    re_path(r'^manuscript/huwa/download/$', ManuscriptHuwaToJson.as_view(), name='manuscript_huwajson'),
    re_path(r'^manuscript/ead/download', ManuEadDownload.as_view(), name='ead_results'),

    re_path(r'^manulink/list', ManuscriptLinkListView.as_view(), name='manuscriptlink_list'),
    re_path(r'^manulink/details(?:/(?P<pk>\d+))?/$', ManuscriptLinkDetails.as_view(), name='manuscriptlink_details'),
    re_path(r'^manulink/edit(?:/(?P<pk>\d+))?/$', ManuscriptLinkEdit.as_view(), name='manuscriptlink_edit'),
    
    re_path(r'^codico/list', CodicoListView.as_view(), name='codico_list'),
    re_path(r'^codico/details(?:/(?P<pk>\d+))?/$', CodicoDetails.as_view(), name='codico_details'),
    re_path(r'^codico/edit(?:/(?P<pk>\d+))?/$', CodicoEdit.as_view(), name='codico_edit'),

    re_path(r'^location/list', LocationListView.as_view(), name='location_list'),
    re_path(r'^location/details(?:/(?P<pk>\d+))?/$', LocationDetails.as_view(), name='location_details'),
    re_path(r'^location/edit(?:/(?P<pk>\d+))?/$', LocationEdit.as_view(), name='location_edit'),

    re_path(r'^origin/list', OriginListView.as_view(), name='origin_list'),
    re_path(r'^origin/details(?:/(?P<pk>\d+))?/$', OriginDetails.as_view(), name='origin_details'),
    re_path(r'^origin/edit(?:/(?P<pk>\d+))?/$', OriginEdit.as_view(), name='origin_edit'),
    re_path(r'^origincod/details(?:/(?P<pk>\d+))?/$', OriginCodDetails.as_view(), name='origincod_details'),
    re_path(r'^origincod/edit(?:/(?P<pk>\d+))?/$', OriginCodEdit.as_view(), name='origincod_edit'),

    re_path(r'^library/list', LibraryListView.as_view(), name='library_list'),
    re_path(r'^library/details(?:/(?P<pk>\d+))?/$', LibraryDetails.as_view(), name='library_details'),
    re_path(r'^library/edit(?:/(?P<pk>\d+))?/$', LibraryEdit.as_view(), name='library_edit'),
    re_path(r'^library/download', LibraryListDownload.as_view(), name='library_results'),
    re_path(r'^library/import/excel/$', LibraryUploadExcel.as_view(), name='library_upload_excel'),

    re_path(r'^ssg/list', EqualGoldListView.as_view(), name='equalgold_list'),
    re_path(r'^ssg/details(?:/(?P<pk>\d+))?/$', EqualGoldDetails.as_view(), name='equalgold_details'),
    re_path(r'^ssg/edit(?:/(?P<pk>\d+))?/$', EqualGoldEdit.as_view(), name='equalgold_edit'),
    re_path(r'^ssg/transdel(?:/(?P<pk>\d+))?/$', EqualGoldTransDel.as_view(), name='equalgold_transdel'),
    re_path(r'^ssg/ukw(?:/(?P<pk>\d+))?/$', EqualGoldUserKeyword.as_view(), name='equalgold_ukw'),
    re_path(r'^ssg/pca(?:/(?P<pk>\d+))?/$', EqualGoldPca.as_view(), name='equalgold_pca'),
    re_path(r'^ssg/graph(?:/(?P<pk>\d+))?/$', EqualGoldGraph.as_view(), name='equalgold_graph'),
    re_path(r'^ssg/trans(?:/(?P<pk>\d+))?/$', EqualGoldTrans.as_view(), name='equalgold_trans'),
    re_path(r'^ssg/overlap(?:/(?P<pk>\d+))?/$', EqualGoldOverlap.as_view(), name='equalgold_overlap'),
    re_path(r'^ssg/attr(?:/(?P<pk>\d+))?/$', EqualGoldAttr.as_view(), name='equalgold_attr'),
    re_path(r'^ssg/origin(?:/(?P<pk>\d+))?/$', EqualGoldOrigin.as_view(), name='equalgold_origin'),
    re_path(r'^ssg/chrono(?:/(?P<pk>\d+))?/$', EqualGoldChrono.as_view(), name='equalgold_chrono'),
    re_path(r'^ssg/huwa/download/$', EqualGoldHuwaToJson.as_view(), name='equalgold_huwajson'),
    re_path(r'^ssg/huwa/literature/$', EqualGoldHuwaLitToJson.as_view(), name='equalgold_huwalitjson'),
    re_path(r'^ssg/huwa/opera/$', EqualGoldHuwaOpera.as_view(), name='equalgold_huwaopera'),
    re_path(r'^ssg/huwa/retractationes/$', EqualGoldHuwaRetr.as_view(), name='equalgold_huwaretr'),
    re_path(r'^ssg/huwa/indiculum/$', EqualGoldHuwaIndiculum.as_view(), name='equalgold_huwaindiculum'),
    re_path(r'^ssg/huwa/nebenwerk/$', EqualGoldHuwaNebenwerk.as_view(), name='equalgold_huwanebenwerk'),
    re_path(r'^ssg/import/edilit/$', EqualGoldUploadEdilit.as_view(), name='equalgold_upload_edilit'),

    re_path(r'^ssg/scount/histo/download', EqualGoldScountDownload.as_view(), name='equalgold_scount_download'),
    re_path(r'^ssg/graph/download(?:/(?P<pk>\d+))?/$', EqualGoldGraphDownload.as_view(), name='equalgold_graph_download'),
    re_path(r'^ssg/trans/download(?:/(?P<pk>\d+))?/$', EqualGoldTransDownload.as_view(), name='equalgold_trans_download'),
    re_path(r'^ssg/overlap/download(?:/(?P<pk>\d+))?/$', EqualGoldOverlapDownload.as_view(), name='equalgold_overlap_download'),
    
    re_path(r'^ssg/af/add/list', EqualAddList.as_view(), name='equaladdall_list'),
    re_path(r'^ssg/af/add/details(?:/(?P<pk>\d+))?/$', EqualAddDetails.as_view(), name='equaladdall_details'),
    re_path(r'^ssg/af/add/edit(?:/(?P<pk>\d+))?/$', EqualAddEdit.as_view(), name='equaladdall_edit'),
        
    re_path(r'^ssg/uaf/add/list', EqualAddUList.as_view(), name='equaladduser_list'),
    re_path(r'^ssg/uaf/add/details(?:/(?P<pk>\d+))?/$', EqualAddUserDetails.as_view(), name='equaladduser_details'),
    re_path(r'^ssg/uaf/add/edit(?:/(?P<pk>\d+))?/$', EqualAddUserEdit.as_view(), name='equaladduser_edit'),
    
    re_path(r'^ssg/af/addapproval/list', EqualAddApprovalList.as_view(), name='equaladdapprovalall_list'),
    re_path(r'^ssg/af/addapproval/details(?:/(?P<pk>\d+))?/$', EqualAddApprovalDetails.as_view(), name='equaladdapprovalall_details'),
    re_path(r'^ssg/af/addapproval/edit(?:/(?P<pk>\d+))?/$', EqualAddApprovalEdit.as_view(), name='equaladdapprovalall_edit'),
        
    re_path(r'^ssg/uaf/addapproval/list', EqualAddApprovalUList.as_view(), name='equaladdapprovaluser_list'),
    re_path(r'^ssg/uaf/addapproval/details(?:/(?P<pk>\d+))?/$', EqualAddApprovalUserDetails.as_view(), name='equaladdapprovaluser_details'),
    re_path(r'^ssg/uaf/addapproval/edit(?:/(?P<pk>\d+))?/$', EqualAddApprovalUserEdit.as_view(), name='equaladdapprovaluser_edit'),    
    
    re_path(r'^ssg/field/change/list', EqualChangeList.as_view(), name='equalchangeall_list'),
    re_path(r'^ssg/field/change/details(?:/(?P<pk>\d+))?/$', EqualChangeDetails.as_view(), name='equalchangeall_details'),
    re_path(r'^ssg/field/change/edit(?:/(?P<pk>\d+))?/$', EqualChangeEdit.as_view(), name='equalchangeall_edit'),

    re_path(r'^ssg/ufield/change/list', EqualChangeUlist.as_view(), name='equalchangeuser_list'),
    re_path(r'^ssg/ufield/change/details(?:/(?P<pk>\d+))?/$', EqualChangeUserDetails.as_view(), name='equalchangeuser_details'),
    re_path(r'^ssg/ufield/change/edit(?:/(?P<pk>\d+))?/$', EqualChangeUserEdit.as_view(), name='equalchangeuser_edit'),

    re_path(r'^ssg/field/approval/list', EqualApprovalList.as_view(), name='equalapprovalall_list'),
    re_path(r'^ssg/field/approval/details(?:/(?P<pk>\d+))?/$', EqualApprovalDetails.as_view(), name='equalapprovalall_details'),
    re_path(r'^ssg/field/approval/edit(?:/(?P<pk>\d+))?/$', EqualApprovalEdit.as_view(), name='equalapprovalall_edit'),
    
    re_path(r'^ssg/ufield/approval/list', EqualApprovalUlist.as_view(), name='equalapprovaluser_list'),
    re_path(r'^ssg/ufield/approval/details(?:/(?P<pk>\d+))?/$', EqualApprovalUserDetails.as_view(), name='equalapprovaluser_details'),
    re_path(r'^ssg/ufield/approval/edit(?:/(?P<pk>\d+))?/$', EqualApprovalUserEdit.as_view(), name='equalapprovaluser_edit'),

    re_path(r'^ssglink/list', EqualGoldLinkListView.as_view(), name='equalgoldlink_list'),
    re_path(r'^ssglink/details(?:/(?P<pk>\d+))?/$', EqualGoldLinkDetails.as_view(), name='equalgoldlink_details'),
    re_path(r'^ssglink/edit(?:/(?P<pk>\d+))?/$', EqualGoldLinkEdit.as_view(), name='equalgoldlink_edit'),
    
    re_path(r'^sermon/list', SermonListView.as_view(), name='sermon_list'),
    re_path(r'^sermon/details(?:/(?P<pk>\d+))?/$', SermonDetails.as_view(), name='sermon_details'),
    re_path(r'^sermon/edit(?:/(?P<pk>\d+))?/$', SermonEdit.as_view(), name='sermon_edit'),
    re_path(r'^sermon/transdel(?:/(?P<pk>\d+))?/$', SermonTransDel.as_view(), name='sermon_transdel'),
    re_path(r'^sermon/move(?:/(?P<pk>\d+))?/$', SermonMove.as_view(), name='sermon_move'),
    re_path(r'^sermon/ukw(?:/(?P<pk>\d+))?/$', SermonUserKeyword.as_view(), name='sermon_ukw'),
        
    re_path(r'^sermolink/list', SermonDescrLinkListView.as_view(), name='sermondescrlink_list'),
    re_path(r'^sermolink/details(?:/(?P<pk>\d+))?/$', SermonDescrLinkDetails.as_view(), name='sermondescrlink_details'),
    re_path(r'^sermolink/edit(?:/(?P<pk>\d+))?/$', SermonDescrLinkEdit.as_view(), name='sermondescrlink_edit'),
    
    re_path(r'^dataset/private/list', CollectionListView.as_view(prefix="priv"), name='collpriv_list'), 
    re_path(r'^dataset/public/list', CollectionListView.as_view(prefix="publ"), name='collpubl_list'),  
    re_path(r'^collection/hist/list', CollectionListView.as_view(prefix="hist"), name='collhist_list'),
    re_path(r'^collection/any/list', CollectionListView.as_view(prefix="any"), name='collany_list'),
    re_path(r'^collection/sermo/list', CollectionListView.as_view(prefix="sermo"), name='collsermo_list'),
    re_path(r'^collection/manu/list', CollectionListView.as_view(prefix="manu"), name='collmanu_list'),
    re_path(r'^collection/gold/list', CollectionListView.as_view(prefix="gold"), name='collgold_list'),
    re_path(r'^collection/super/list', CollectionListView.as_view(prefix="super"), name='collsuper_list'),

    re_path(r'^dataset/private/details(?:/(?P<pk>\d+))?/$', CollPrivDetails.as_view(), name='collpriv_details'),
    re_path(r'^dataset/public/details(?:/(?P<pk>\d+))?/$', CollPublDetails.as_view(), name='collpubl_details'), 
    re_path(r'^collection/hist/details(?:/(?P<pk>\d+))?/$', CollHistDetails.as_view(), name='collhist_details'),
    re_path(r'^collection/any/details(?:/(?P<pk>\d+))?/$', CollAnyDetails.as_view(), name='collany_details'),
    re_path(r'^collection/sermo/details(?:/(?P<pk>\d+))?/$', CollSermoDetails.as_view(), name='collsermo_details'),
    re_path(r'^collection/manu/details(?:/(?P<pk>\d+))?/$', CollManuDetails.as_view(), name='collmanu_details'),
    re_path(r'^collection/gold/details(?:/(?P<pk>\d+))?/$', CollGoldDetails.as_view(), name='collgold_details'),
    re_path(r'^collection/super/details(?:/(?P<pk>\d+))?/$', CollSuperDetails.as_view(), name='collsuper_details'),

    re_path(r'^dataset/private/edit(?:/(?P<pk>\d+))?/$', CollPrivEdit.as_view(), name='collpriv_edit'),
    re_path(r'^dataset/public/edit(?:/(?P<pk>\d+))?/$', CollPublEdit.as_view(), name='collpubl_edit'), 
    re_path(r'^collection/hist/edit(?:/(?P<pk>\d+))?/$', CollHistEdit.as_view(), name='collhist_edit'),
    re_path(r'^collection/any/edit(?:/(?P<pk>\d+))?/$', CollAnyEdit.as_view(), name='collany_edit'),
    re_path(r'^collection/sermo/edit(?:/(?P<pk>\d+))?/$', CollSermoEdit.as_view(), name='collsermo_edit'),
    re_path(r'^collection/manu/edit(?:/(?P<pk>\d+))?/$', CollManuEdit.as_view(), name='collmanu_edit'),
    re_path(r'^collection/gold/edit(?:/(?P<pk>\d+))?/$', CollGoldEdit.as_view(), name='collgold_edit'),
    re_path(r'^collection/super/edit(?:/(?P<pk>\d+))?/$', CollSuperEdit.as_view(), name='collsuper_edit'),
    
    re_path(r'^dataset/elevate(?:/(?P<pk>\d+))?/$', CollHistElevate.as_view(), name='collhist_elevate'),
    re_path(r'^collection/hist/manuscript(?:/(?P<pk>\d+))?/$', CollHistManu.as_view(), name='collhist_manu'),
    re_path(r'^collection/hist/template(?:/(?P<pk>\d+))?/$', CollHistTemp.as_view(), name='collhist_temp'),
    re_path(r'^collection/hist/compare(?:/(?P<pk>\d+))?/$', CollHistCompare.as_view(), name='collhist_compare'),
    
    re_path(r'^basket/sermo/update', BasketUpdate.as_view(), name='basket_update'),
    re_path(r'^basket/sermo/show', BasketView.as_view(), name='basket_show'),

    re_path(r'^basket/manu/update', BasketUpdateManu.as_view(), name='basket_update_manu'),
    re_path(r'^basket/manu/show', BasketViewManu.as_view(), name='basket_show_manu'),

    re_path(r'^basket/gold/update', BasketUpdateGold.as_view(), name='basket_update_gold'),
    re_path(r'^basket/gold/show', BasketViewGold.as_view(), name='basket_show_gold'),

    re_path(r'^basket/super/update', BasketUpdateSuper.as_view(), name='basket_update_super'),
    re_path(r'^basket/super/show', BasketViewSuper.as_view(), name='basket_show_super'),
    
    re_path(r'^author/list', AuthorListView.as_view(), name='author_list'),
    re_path(r'^author/details(?:/(?P<pk>\d+))?/$', AuthorDetails.as_view(), name='author_details'),
    re_path(r'^author/edit(?:/(?P<pk>\d+))?/$', AuthorEdit.as_view(), name='author_edit'),
    re_path(r'^author/download', AuthorListDownload.as_view(), name='author_results'),

    re_path(r'^report/list', ReportListView.as_view(), name='report_list'),
    re_path(r'^report/details(?:/(?P<pk>\d+))?/$', ReportDetails.as_view(), name='report_details'),
    re_path(r'^report/edit(?:/(?P<pk>\d+))?/$', ReportEdit.as_view(), name='report_edit'),
    re_path(r'^report/download(?:/(?P<pk>\d+))?/$', ReportDownload.as_view(), name='report_results'),

    re_path(r'^literature/list', LitRefListView.as_view(), name='literature_list'),

    re_path(r'^keyword/list', KeywordListView.as_view(), name='keyword_list'),
    re_path(r'^keyword/details(?:/(?P<pk>\d+))?/$', KeywordDetails.as_view(), name='keyword_details'),
    re_path(r'^keyword/edit(?:/(?P<pk>\d+))?/$', KeywordEdit.as_view(), name='keyword_edit'),

    re_path(r'^userkeyword/list', UserKeywordListView.as_view(), name='userkeyword_list'),
    re_path(r'^userkeyword/details(?:/(?P<pk>\d+))?/$', UserKeywordDetails.as_view(), name='userkeyword_details'),
    re_path(r'^userkeyword/edit(?:/(?P<pk>\d+))?/$', UserKeywordEdit.as_view(), name='userkeyword_edit'),
    re_path(r'^userkeyword/submit(?:/(?P<pk>\d+))?/$', UserKeywordSubmit.as_view(), name='userkeyword_submit'),

    re_path(r'^provenance/list', ProvenanceListView.as_view(), name='provenance_list'),
    re_path(r'^provenance/details(?:/(?P<pk>\d+))?/$', ProvenanceDetails.as_view(), name='provenance_details'),
    re_path(r'^provenance/edit(?:/(?P<pk>\d+))?/$', ProvenanceEdit.as_view(), name='provenance_edit'),
    re_path(r'^provman/details(?:/(?P<pk>\d+))?/$', ProvenanceManDetails.as_view(), name='provenanceman_details'),
    re_path(r'^provman/edit(?:/(?P<pk>\d+))?/$', ProvenanceManEdit.as_view(), name='provenanceman_edit'),
    re_path(r'^provcod/details(?:/(?P<pk>\d+))?/$', ProvenanceCodDetails.as_view(), name='provenancecod_details'),
    re_path(r'^provcod/edit(?:/(?P<pk>\d+))?/$', ProvenanceCodEdit.as_view(), name='provenancecod_edit'),

    re_path(r'^comment/list', CommentListView.as_view(), name='comment_list'),
    re_path(r'^comment/details(?:/(?P<pk>\d+))?/$', CommentDetails.as_view(), name='comment_details'),
    re_path(r'^comment/edit(?:/(?P<pk>\d+))?/$', CommentEdit.as_view(), name='comment_edit'),
    re_path(r'^comment/response/details(?:/(?P<pk>\d+))?/$', CommentResponseDetails.as_view(), name='commentresponse_details'),
    re_path(r'^comment/response/edit(?:/(?P<pk>\d+))?/$', CommentResponseEdit.as_view(), name='commentresponse_edit'),
    re_path(r'^comment/response/send(?:/(?P<pk>\d+))?/$', CommentResponseSend.as_view(), name='commentresponse_send'),

    re_path(r'^bibrange/list', BibRangeListView.as_view(), name='bibrange_list'),
    re_path(r'^bibrange/details(?:/(?P<pk>\d+))?/$', BibRangeDetails.as_view(), name='bibrange_details'),
    re_path(r'^bibrange/edit(?:/(?P<pk>\d+))?/$', BibRangeEdit.as_view(), name='bibrange_edit'),

    re_path(r'^feast/list', FeastListView.as_view(), name='feast_list'),
    re_path(r'^feast/details(?:/(?P<pk>\d+))?/$', FeastDetails.as_view(), name='feast_details'),
    re_path(r'^feast/edit(?:/(?P<pk>\d+))?/$', FeastEdit.as_view(), name='feast_edit'),

    re_path(r'^profile/list', ProfileListView.as_view(), name='profile_list'),
    re_path(r'^profile/details(?:/(?P<pk>\d+))?/$', ProfileDetails.as_view(), name='profile_details'),
    re_path(r'^profile/edit(?:/(?P<pk>\d+))?/$', ProfileEdit.as_view(), name='profile_edit'),
    re_path(r'^default/details(?:/(?P<pk>\d+))?/$', DefaultDetails.as_view(), name='default_details'), 
    re_path(r'^default/edit(?:/(?P<pk>\d+))?/$', DefaultEdit.as_view(), name='default_edit'), 
    re_path(r'^user/details(?:/(?P<pk>\d+))?/$', UserDetails.as_view(), name='user_details'),
    re_path(r'^user/edit(?:/(?P<pk>\d+))?/$', UserEdit.as_view(), name='user_edit'),

    re_path(r'^project/list', ProjectListView.as_view(), name='project2_list'), 
    re_path(r'^project/details(?:/(?P<pk>\d+))?/$', ProjectDetails.as_view(), name='project2_details'), 
    re_path(r'^project/edit(?:/(?P<pk>\d+))?/$', ProjectEdit.as_view(), name='project2_edit'), 

    re_path(r'^source/list', SourceListView.as_view(), name='source_list'),
    re_path(r'^source/details(?:/(?P<pk>\d+))?/$', SourceDetails.as_view(), name='source_details'),
    re_path(r'^source/edit(?:/(?P<pk>\d+))?/$', SourceEdit.as_view(), name='source_edit'),

    re_path(r'^onlinesource/list', OnlineSourceListView.as_view(), name='onlinesources_list'),
    re_path(r'^onlinesource/details(?:/(?P<pk>\d+))?/$', OnlineSourceDetails.as_view(), name='onlinesources_details'),
    re_path(r'^onlinesource/edit(?:/(?P<pk>\d+))?/$', OnlineSourceEdit.as_view(), name='onlinesources_edit'),

    re_path(r'^template/list', TemplateListView.as_view(), name='template_list'),
    re_path(r'^template/details(?:/(?P<pk>\d+))?/$', TemplateDetails.as_view(), name='template_details'),
    re_path(r'^template/edit(?:/(?P<pk>\d+))?/$', TemplateEdit.as_view(), name='template_edit'),
    re_path(r'^template/apply(?:/(?P<pk>\d+))?/$', TemplateApply.as_view(), name='template_apply'),
    re_path(r'^template/import/$', TemplateImport.as_view(), name='template_import'),

    re_path(r'^gold/list', SermonGoldListView.as_view(), name='gold_list'),
    re_path(r'^gold/list', SermonGoldListView.as_view(), name='search_gold'),
    re_path(r'^gold/details(?:/(?P<pk>\d+))?/$', SermonGoldDetails.as_view(), name='gold_details'),
    re_path(r'^gold/edit(?:/(?P<pk>\d+))?/$', SermonGoldEdit.as_view(), name='gold_edit'),
    re_path(r'^gold/import/json/$', SermonGoldUploadJson.as_view(), name='gold_upload_json'),
    re_path(r'^gold/ukw(?:/(?P<pk>\d+))?/$', SermonGoldUserKeyword.as_view(), name='gold_ukw'),

    # ------------ DCT tool ------------------------------------------------------------------------------
    re_path(r'^rset/list', ResearchSetListView.as_view(), name='researchset_list'),
    re_path(r'^rset/details(?:/(?P<pk>\d+))?/$', ResearchSetDetails.as_view(), name='researchset_details'),
    re_path(r'^rset/edit(?:/(?P<pk>\d+))?/$', ResearchSetEdit.as_view(), name='researchset_edit'),

    re_path(r'^dct/list', SetDefListView.as_view(), name='setdef_list'),
    re_path(r'^dct/details(?:/(?P<pk>\d+))?/$', SetDefDetails.as_view(), name='setdef_details'),
    re_path(r'^dct/edit(?:/(?P<pk>\d+))?/$', SetDefEdit.as_view(), name='setdef_edit'),
    re_path(r'^dct/data(?:/(?P<pk>\d+))?/$', SetDefData.as_view(), name='setdef_data'),
    re_path(r'^dct/download(?:/(?P<pk>\d+))?/$', SetDefDownload.as_view(), name='setdef_download'),

    re_path(r'^sgroup/list', SaveGroupListView.as_view(), name='savegroup_list'),
    re_path(r'^sgroup/details(?:/(?P<pk>\d+))?/$', SaveGroupDetails.as_view(), name='savegroup_details'),
    re_path(r'^sgroup/edit(?:/(?P<pk>\d+))?/$', SaveGroupEdit.as_view(), name='savegroup_edit'),

    re_path(r'^importset/list', ImportSetListView.as_view(), name='importset_list'),
    re_path(r'^importset/details(?:/(?P<pk>\d+))?/$', ImportSetDetails.as_view(), name='importset_details'),
    re_path(r'^importset/edit(?:/(?P<pk>\d+))?/$', ImportSetEdit.as_view(), name='importset_edit'),
    re_path(r'^importset/process(?:/(?P<pk>\d+))?/$', ImportSetProcess.as_view(), name='importset_process'),
    re_path(r'^importset/download(?:/(?P<pk>\d+))?/$', ImportSetDownload.as_view(), name='importset_download'),
    re_path(r'^importset/manu/template$', ImportSetManuTempDownload.as_view(), name='importset_manu_template'),

    re_path(r'^importreview/list', ImportReviewListView.as_view(), name='importreview_list'),
    re_path(r'^importreview/details(?:/(?P<pk>\d+))?/$', ImportReviewDetails.as_view(), name='importreview_details'),
    re_path(r'^importreview/edit(?:/(?P<pk>\d+))?/$', ImportReviewEdit.as_view(), name='importreview_edit'),
    re_path(r'^importreview/process(?:/(?P<pk>\d+))?/$', ImportReviewProcess.as_view(), name='importreview_process'),

    # ------------ Stemmatology tool ---------------------------------------------------------------------
    re_path(r'^stemmaset/list', StemmaSetListView.as_view(), name='stemmaset_list'),
    re_path(r'^stemmaset/details(?:/(?P<pk>\d+))?/$', StemmaSetDetails.as_view(), name='stemmaset_details'),
    re_path(r'^stemmaset/edit(?:/(?P<pk>\d+))?/$', StemmaSetEdit.as_view(), name='stemmaset_edit'),
    re_path(r'^stemmaset/add(?:/(?P<pk>\d+))?/$', StemmaSetAdd.as_view(), name='stemmaset_add'),

    re_path(r'^stemmaset/dashboard(?:/(?P<pk>\d+))?/$', StemmaDashboard.as_view(), name='stemmaset_dashboard'),
    re_path(r'^stemmacalc/start(?:/(?P<pk>\d+))?/$', StemmaStart.as_view(), name='stemma_start'),
    re_path(r'^stemmacalc/progress(?:/(?P<pk>\d+))?/$', StemmaProgress.as_view(), name='stemma_progress'),
    re_path(r'^stemmacalc/download(?:/(?P<pk>\d+))?/$', StemmaDownload.as_view(), name='stemma_download'),

    # ------------ My Passim PRE -------------------------------------------------------------------------
    re_path(r'^mypassim/details', MyPassimDetails.as_view(), name='mypassim_details'),
    re_path(r'^mypassim/edit', MyPassimEdit.as_view(), name='mypassim_edit'),

    re_path(r'^savedsearch/apply(?:/(?P<pk>\d+))?/$', SavedSearchApply.as_view(), name='savedsearch_apply'),
    re_path(r'^savedvis/apply(?:/(?P<pk>\d+))?/$', SavedVisualizationApply.as_view(), name='savedvis_apply'),
    re_path(r'^saveditem/apply(?:/(?P<pk>\d+))?/$', SavedItemApply.as_view(), name='saveditem_apply'),
    re_path(r'^selitem/apply(?:/(?P<pk>\d+))?/$', SelectItemApply.as_view(), name='selitem_apply'),
    re_path(r'^savegroup/apply(?:/(?P<pk>\d+))?/$', SaveGroupApply.as_view(), name='savegroup_apply'),

    re_path(r'^api/countries/$', passim.seeker.views.get_countries, name='api_countries'),
    re_path(r'^api/cities/$', passim.seeker.views.get_cities, name='api_cities'),
    re_path(r'^api/libraries/$', passim.seeker.views.get_libraries, name='api_libraries'),
    re_path(r'^api/origins/$', passim.seeker.views.get_origins, name='api_origins'),
    re_path(r'^api/locations/$', passim.seeker.views.get_locations, name='api_locations'),
    re_path(r'^api/litrefs/$', passim.seeker.views.get_litrefs, name='api_litrefs'),
    re_path(r'^api/litref/$', passim.seeker.views.get_litref, name='api_litref'),
    re_path(r'^api/sg/$', passim.seeker.views.get_sg, name='api_sg'),
    re_path(r'^api/sglink/$', passim.seeker.views.get_sglink, name='api_sglink'),
    re_path(r'^api/ssglink/$', passim.seeker.views.get_ssglink, name='api_ssglink'),
    re_path(r'^api/ssg2ssg/$', passim.seeker.views.get_ssg2ssg, name='api_ssg2ssg'),
    re_path(r'^api/ssg/$', passim.seeker.views.get_ssg, name='api_ssg'),
    re_path(r'^api/ssgdist/$', passim.seeker.views.get_ssgdist, name='api_ssgdist'),
    re_path(r'^api/sermosig/$', passim.seeker.views.get_sermosig, name='api_sermosig'),
    re_path(r'^api/manuscripts/$', passim.seeker.views.get_manuscripts, name='api_manuscripts'),
    re_path(r'^api/authors/list/$', passim.seeker.views.get_authors, name='api_authors'),
    re_path(r'^api/nicknames/$', passim.seeker.views.get_nicknames, name='api_nicknames'),
    re_path(r'^api/eqgincipits/$', passim.seeker.views.get_eqgincipits, name='api_eqgincipits'),
    re_path(r'^api/eqgexplicits/$', passim.seeker.views.get_eqgexplicits, name='api_eqgexplicits'),
    re_path(r'^api/gldincipits/$', passim.seeker.views.get_gldincipits, name='api_gldincipits'),
    re_path(r'^api/gldexplicits/$', passim.seeker.views.get_gldexplicits, name='api_gldexplicits'),
    re_path(r'^api/srmincipits/$', passim.seeker.views.get_srmincipits, name='api_srmincipits'),
    re_path(r'^api/srmexplicits/$', passim.seeker.views.get_srmexplicits, name='api_srmexplicits'),
    re_path(r'^api/gldsignatures/$', passim.seeker.views.get_gldsignatures, name='api_gldsignatures'),
    re_path(r'^api/srmsignatures/$', passim.seeker.views.get_srmsignatures, name='api_srmsignatures'),
    re_path(r'^api/editions/$', passim.seeker.views.get_editions, name='api_editions'),
    re_path(r'^api/keywords/$', passim.seeker.views.get_keywords, name='api_keywords'),
    re_path(r'^api/collections/$', passim.seeker.views.get_collections, name='api_collections'),
    re_path(r'^api/manuidnos/$', passim.seeker.views.get_manuidnos, name='api_manuidnos'),

    re_path(r'^api/import/authors/$', passim.seeker.views.import_authors, name='import_authors'),
    re_path(r'^api/import/gold/$', passim.seeker.views.import_gold, name='import_gold'),

    re_path(r'^api/import/pdf_lit/$', passim.seeker.views.do_create_pdf_lit, name='create_pdf_lit'), 
    re_path(r'^api/import/pdf_edi/$', passim.seeker.views.do_create_pdf_edi, name='create_pdf_edi'), 
    re_path(r'^api/import/pdf_manu/$', passim.seeker.views.do_create_pdf_manu, name='create_pdf_manu'),
     
    re_path(r'^api/search/ecodex/$', passim.seeker.views.search_ecodex, name='search_ecodex'),
    re_path(r'^api/gold/get(?:/(?P<pk>\d+))?/$', passim.seeker.views.get_gold, name='get_gold'),
    re_path(r'^api/comment/send/$', CommentSend.as_view(), name='comment_send'),

    # ================ CMS ========================================================================
    re_path(r'^cpage/list', CpageListView.as_view(), name='cpage_list'),
    re_path(r'^cpage/details(?:/(?P<pk>\d+))?/$', CpageDetails.as_view(), name='cpage_details'),
    re_path(r'^cpage/edit(?:/(?P<pk>\d+))?/$', CpageEdit.as_view(), name='cpage_edit'),
    re_path(r'^cpage/clocation/add(?:/(?P<pk>\d+))?/$', CpageAdd.as_view(), name='cpage_add_loc'),

    re_path(r'^clocation/list', ClocationListView.as_view(), name='clocation_list'),
    re_path(r'^clocation/details(?:/(?P<pk>\d+))?/$', ClocationDetails.as_view(), name='clocation_details'),
    re_path(r'^clocation/edit(?:/(?P<pk>\d+))?/$', ClocationEdit.as_view(), name='clocation_edit'),
    re_path(r'^clocation/citem/add(?:/(?P<pk>\d+))?/$', ClocationAdd.as_view(), name='clocation_add_item'),

    re_path(r'^citem/list', CitemListView.as_view(), name='citem_list'),
    re_path(r'^citem/details(?:/(?P<pk>\d+))?/$', CitemDetails.as_view(), name='citem_details'),
    re_path(r'^citem/edit(?:/(?P<pk>\d+))?/$', CitemEdit.as_view(), name='citem_edit'),

    # ================ Any READER APP URLs should come here =======================================
    re_path(r'^reader/import/ecodex/$', ReaderEcodex.as_view(), name='import_ecodex'),
    re_path(r'^reader/import/ead/$', ReaderEad.as_view(), name='import_ead'),
    re_path(r'^reader/import/huwa/$', ReaderHuwaImport.as_view(), name='import_huwa'),
    re_path(r'^reader/import/trans/ssg/$', ReaderTransEqgImport.as_view(), name='import_trans_eqg'),
    re_path(r'^reader/import/cppm_af/$', passim.reader.views.reader_CPPM_AF, name='import_cppm_af'),     
    re_path(r'^reader/import/cppm_manu/$', passim.reader.views.reader_CPPM_manu, name='import_cppm_manuscripts'), 
    # =============================================================================================

    # ============== ENRICH STUFF =================================================
    re_path(r'^enrich/speaker/list', SpeakerListView.as_view(), name='speaker_list'),
    re_path(r'^enrich/speaker/details(?:/(?P<pk>\d+))?/$', SpeakerDetails.as_view(), name='speaker_details'),
    re_path(r'^enrich/speaker/edit(?:/(?P<pk>\d+))?/$', SpeakerEdit.as_view(), name='speaker_edit'),

    re_path(r'^enrich/sentence/list', SentenceListView.as_view(), name='sentence_list'),
    re_path(r'^enrich/sentence/details(?:/(?P<pk>\d+))?/$', SentenceDetails.as_view(), name='sentence_details'),
    re_path(r'^enrich/sentence/edit(?:/(?P<pk>\d+))?/$', SentenceEdit.as_view(), name='sentence_edit'),

    re_path(r'^enrich/unit/list', TestunitListView.as_view(), name='testunit_list'),
    re_path(r'^enrich/unit/details(?:/(?P<pk>\d+))?/$', TestunitDetails.as_view(), name='testunit_details'),
    re_path(r'^enrich/unit/edit(?:/(?P<pk>\d+))?/$', TestunitEdit.as_view(), name='testunit_edit'),
    re_path(r'^enrich/unit/run', TestunitRunView.as_view(), name='testunit_run'),

    re_path(r'^enrich/set/list', TestsetListView.as_view(), name='testset_list'),
    re_path(r'^enrich/set/details(?:/(?P<pk>\d+))?/$', TestsetDetails.as_view(), name='testset_details'),
    re_path(r'^enrich/set/edit(?:/(?P<pk>\d+))?/$', TestsetEdit.as_view(), name='testset_edit'),
    re_path(r'^enrich/download', TestsetDownload.as_view(), name='testset_results'),
    re_path(r'^api/enrich/testsets/$', passim.enrich.views.get_testsets, name='api_testsets'),

    # =============================================================================================
    # For working with ModelWidgets from the select2 package https://django-select2.readthedocs.io
    re_path(r'^select2/', django.urls.conf.include('django_select2.urls')),

    # ========================= PLUGIN ============================================================
    re_path(r'^plugin/sermboard/$', passim.plugin.views.sermonboard, name='sermonboard'),
    path('plugin/apply/', BoardApply.as_view(),  name='board_apply'),
    ## My plotly apps
    #path('simple', TemplateView.as_view(template_name='plugin/simple.html'), name="simple"),
    #path('plugin/dashboard', TemplateView.as_view(template_name='plugin/dashboard.html'), name="dashboard"),
    ## Needed for django-plotly-dash
    #path('django_plotly_dash/', include('django_plotly_dash.urls')),

    # =============================================================================================
    re_path(r'^definitions$', RedirectView.as_view(url='/'+pfx+'admin/'), name='definitions'),
    re_path(r'^signup/$', passim.seeker.views.signup, name='signup'),

    re_path(r'^login/user/(?P<user_id>\w[\w\d\-_]+)$', passim.seeker.views.login_as_user, name='login_as'),

    re_path(r'^login/$', LoginView.as_view
        (
            template_name= 'login.html',
            authentication_form= passim.seeker.forms.BootstrapAuthenticationForm,
            extra_context= {'title': 'Log in','year': datetime.now().year,}
        ),
        name='login'),
    re_path(r'^logout$',  LogoutView.as_view(next_page=reverse_lazy('home')), name='logout'),

    # Uncomment the next line to enable the admin:
    re_path(r'^admin/', admin.site.urls, name='admin_base'),
] 

if USE_DASH:
    print("Using dash")
    lst_dash = [
        # My plotly apps
        path('simple', TemplateView.as_view(template_name='plugin/simple.html'), name="simple"),
        path('plugin/dashboard', TemplateView.as_view(template_name='plugin/dashboard.html'), name="dashboard"),
        # Needed for django-plotly-dash
        path('django_plotly_dash/', include('django_plotly_dash.urls')),
    ]
    for oItem in lst_dash:
        urlpatterns.append(oItem)