"""
Definition of urls for passim.
"""

from datetime import datetime
from django.contrib.auth.decorators import login_required, permission_required
from django.conf.urls import include, url # , handler404, handler400, handler403, handler500
from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from django.http import HttpResponseNotFound
from django.urls import path
import django.contrib.auth.views
import django

import passim.seeker.forms
import passim.seeker.views
import passim.reader.views
from passim import views
from passim.seeker.views import *
from passim.seeker.visualizations import *
from passim.dct.views import *
from passim.reader.views import *
from passim.enrich.views import *
from passim.reader.excel import ManuscriptUploadExcel, ManuscriptUploadJson, ManuscriptUploadGalway

# Import from PASSIM as a whole
from passim.settings import APP_PREFIX

# Other Django stuff
# from django.core import urlresolvers
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.base import RedirectView

admin.autodiscover()


# Set admin stie information
admin.site.site_header = "Patristic Sermons in the Middle Ages"
admin.site.site_title = "passim Admin"

pfx = APP_PREFIX
use_testapp = False

# ================ Custom error handling when debugging =============
def custom_page_not_found(request):
    return passim.seeker.views.view_404(request)

urlpatterns = [
    # Examples:
    url(r'^$', passim.seeker.views.home, name='home'),
    # url(r'^404/$', passim.seeker.views.view_404, name='view_404'),
    path("404/", custom_page_not_found),
    url(r'^favicon\.ico$',RedirectView.as_view(url='/static/seeker/content/favicon.ico')),
    url(r'^contact$', passim.seeker.views.contact, name='contact'),
    url(r'^about', passim.seeker.views.about, name='about'),
    url(r'^short', passim.seeker.views.about, name='short'),
    url(r'^guide', passim.seeker.views.guide, name='guide'),
    url(r'^mypassim', passim.dct.views.mypassim, name='mypassim'),
    url(r'^technical', passim.seeker.views.technical, name='technical'),
    url(r'^bibliography', passim.seeker.views.bibliography, name='bibliography'),
    url(r'^nlogin', passim.seeker.views.nlogin, name='nlogin'),

    url(r'^sync/passim/$', passim.seeker.views.sync_passim, name='sync_passim'),
    url(r'^sync/start/$', passim.seeker.views.sync_start, name='sync_start'),
    url(r'^sync/progress/$', passim.seeker.views.sync_progress, name='sync_progress'),
    url(r'^sync/zotero/$', passim.seeker.views.redo_zotero, name='sync_zotero'),

    url(r'^tools/clavis/$', passim.seeker.views.do_clavis, name='do_clavis'),
    url(r'^tools/goldtogold/$', passim.seeker.views.do_goldtogold, name='do_goldtogold'),
    url(r'^tools/goldsearch/$', passim.seeker.views.do_goldsearch, name='do_goldsearch'),
    url(r'^tools/stype/$', passim.seeker.views.do_stype, name='do_stype'),
    url(r'^tools/locations/$', passim.seeker.views.do_locations, name='do_locations'),
    url(r'^tools/provenance/$', passim.seeker.views.do_provenance, name='do_provenance'),
    url(r'^tools/daterange/$', passim.seeker.views.do_daterange, name='do_daterange'),
    url(r'^tools/mext/$', passim.seeker.views.do_mext, name='do_mext'),
    url(r'^tools/sermons/$', passim.seeker.views.do_sermons, name='do_sermons'),
    url(r'^tools/ssg/$', passim.seeker.views.do_ssgmigrate, name='do_ssgmigrate'),
    url(r'^tools/huwa/$', passim.seeker.views.do_huwa, name='do_huwa'),

    url(r'^search/sermon', SermonListView.as_view(), name='search_sermon'),
    url(r'^search/manuscript', ManuscriptListView.as_view(), name='search_manuscript'),
    url(r'^search/collection',  CollectionListView.as_view(prefix="any"), name='search_collection'),
    url(r'^search/library', LibraryListView.as_view(), name='library_search'),
    url(r'^search/author', AuthorListView.as_view(), name='author_search'),

    url(r'^libraries/download', LibraryListDownload.as_view(), name='library_results'),
    url(r'^authors/download', AuthorListDownload.as_view(), name='author_results'),
    url(r'^manuscript/ead/download', ManuEadDownload.as_view(), name='ead_results'),

    url(r'^manuscript/list', ManuscriptListView.as_view(), name='manuscript_list'),
    url(r'^manuscript/details(?:/(?P<pk>\d+))?/$', ManuscriptDetails.as_view(), name='manuscript_details'),
    url(r'^manuscript/edit(?:/(?P<pk>\d+))?/$', ManuscriptEdit.as_view(), name='manuscript_edit'),
    url(r'^manuscript/hierarchy(?:/(?P<pk>\d+))?/$', ManuscriptHierarchy.as_view(), name='manuscript_hierarchy'),
    url(r'^manuscript/download(?:/(?P<pk>\d+))?/$', ManuscriptDownload.as_view(), name='manuscript_download'),
    url(r'^manuscript/import/excel/$', ManuscriptUploadExcel.as_view(), name='manuscript_upload_excel'),
    url(r'^manuscript/import/json/$', ManuscriptUploadJson.as_view(), name='manuscript_upload_json'),
    url(r'^manuscript/import/galway/$', ManuscriptUploadGalway.as_view(), name='manuscript_upload_galway'),
    url(r'^manuscript/codico/$', ManuscriptCodico.as_view(), name='manuscript_codico'),

    url(r'^codico/list', CodicoListView.as_view(), name='codico_list'),
    url(r'^codico/details(?:/(?P<pk>\d+))?/$', CodicoDetails.as_view(), name='codico_details'),
    url(r'^codico/edit(?:/(?P<pk>\d+))?/$', CodicoEdit.as_view(), name='codico_edit'),

    url(r'^location/list', LocationListView.as_view(), name='location_list'),
    url(r'^location/details(?:/(?P<pk>\d+))?/$', LocationDetails.as_view(), name='location_details'),
    url(r'^location/edit(?:/(?P<pk>\d+))?/$', LocationEdit.as_view(), name='location_edit'),

    url(r'^origin/list', OriginListView.as_view(), name='origin_list'),
    url(r'^origin/details(?:/(?P<pk>\d+))?/$', OriginDetails.as_view(), name='origin_details'),
    url(r'^origin/edit(?:/(?P<pk>\d+))?/$', OriginEdit.as_view(), name='origin_edit'),

    url(r'^library/list', LibraryListView.as_view(), name='library_list'),
    url(r'^library/details(?:/(?P<pk>\d+))?/$', LibraryDetails.as_view(), name='library_details'),
    url(r'^library/edit(?:/(?P<pk>\d+))?/$', LibraryEdit.as_view(), name='library_edit'),

    url(r'^ssg/list', EqualGoldListView.as_view(), name='equalgold_list'),
    url(r'^ssg/details(?:/(?P<pk>\d+))?/$', EqualGoldDetails.as_view(), name='equalgold_details'),
    url(r'^ssg/edit(?:/(?P<pk>\d+))?/$', EqualGoldEdit.as_view(), name='equalgold_edit'),
    url(r'^ssg/pca(?:/(?P<pk>\d+))?/$', EqualGoldPca.as_view(), name='equalgold_pca'),
    url(r'^ssg/graph(?:/(?P<pk>\d+))?/$', EqualGoldGraph.as_view(), name='equalgold_graph'),
    url(r'^ssg/trans(?:/(?P<pk>\d+))?/$', EqualGoldTrans.as_view(), name='equalgold_trans'),
    url(r'^ssg/overlap(?:/(?P<pk>\d+))?/$', EqualGoldOverlap.as_view(), name='equalgold_overlap'),

    url(r'^ssg/scount/histo/download', EqualGoldScountDownload.as_view(), name='equalgold_scount_download'),
    url(r'^ssg/graph/download(?:/(?P<pk>\d+))?/$', EqualGoldGraphDownload.as_view(), name='equalgold_graph_download'),
    url(r'^ssg/trans/download(?:/(?P<pk>\d+))?/$', EqualGoldTransDownload.as_view(), name='equalgold_trans_download'),
    url(r'^ssg/overlap/download(?:/(?P<pk>\d+))?/$', EqualGoldOverlapDownload.as_view(), name='equalgold_overlap_download'),

    url(r'^sermon/details(?:/(?P<pk>\d+))?/$', SermonDetails.as_view(), name='sermon_details'),
    url(r'^sermon/edit(?:/(?P<pk>\d+))?/$', SermonEdit.as_view(), name='sermon_edit'),
    url(r'^sermon/list', SermonListView.as_view(), name='sermon_list'),
    
    url(r'^dataset/private/list', CollectionListView.as_view(prefix="priv"), name='collpriv_list'),
    url(r'^dataset/public/list', CollectionListView.as_view(prefix="publ"), name='collpubl_list'),
    url(r'^collection/hist/list', CollectionListView.as_view(prefix="hist"), name='collhist_list'),
    url(r'^collection/any/list', CollectionListView.as_view(prefix="any"), name='collany_list'),
    url(r'^collection/sermo/list', CollectionListView.as_view(prefix="sermo"), name='collsermo_list'),
    url(r'^collection/manu/list', CollectionListView.as_view(prefix="manu"), name='collmanu_list'),
    url(r'^collection/gold/list', CollectionListView.as_view(prefix="gold"), name='collgold_list'),
    url(r'^collection/super/list', CollectionListView.as_view(prefix="super"), name='collsuper_list'),

    url(r'^dataset/private/details(?:/(?P<pk>\d+))?/$', CollPrivDetails.as_view(), name='collpriv_details'),
    url(r'^dataset/public/details(?:/(?P<pk>\d+))?/$', CollPublDetails.as_view(), name='collpubl_details'),
    url(r'^collection/hist/details(?:/(?P<pk>\d+))?/$', CollHistDetails.as_view(), name='collhist_details'),
    url(r'^collection/any/details(?:/(?P<pk>\d+))?/$', CollAnyDetails.as_view(), name='collany_details'),
    url(r'^collection/sermo/details(?:/(?P<pk>\d+))?/$', CollSermoDetails.as_view(), name='collsermo_details'),
    url(r'^collection/manu/details(?:/(?P<pk>\d+))?/$', CollManuDetails.as_view(), name='collmanu_details'),
    url(r'^collection/gold/details(?:/(?P<pk>\d+))?/$', CollGoldDetails.as_view(), name='collgold_details'),
    url(r'^collection/super/details(?:/(?P<pk>\d+))?/$', CollSuperDetails.as_view(), name='collsuper_details'),

    url(r'^dataset/private/edit(?:/(?P<pk>\d+))?/$', CollPrivEdit.as_view(), name='collpriv_edit'),
    url(r'^dataset/public/edit(?:/(?P<pk>\d+))?/$', CollPublEdit.as_view(), name='collpubl_edit'),
    url(r'^collection/hist/edit(?:/(?P<pk>\d+))?/$', CollHistEdit.as_view(), name='collhist_edit'),
    url(r'^collection/any/edit(?:/(?P<pk>\d+))?/$', CollAnyEdit.as_view(), name='collany_edit'),
    url(r'^collection/sermo/edit(?:/(?P<pk>\d+))?/$', CollSermoEdit.as_view(), name='collsermo_edit'),
    url(r'^collection/manu/edit(?:/(?P<pk>\d+))?/$', CollManuEdit.as_view(), name='collmanu_edit'),
    url(r'^collection/gold/edit(?:/(?P<pk>\d+))?/$', CollGoldEdit.as_view(), name='collgold_edit'),
    url(r'^collection/super/edit(?:/(?P<pk>\d+))?/$', CollSuperEdit.as_view(), name='collsuper_edit'),
    
    url(r'^dataset/elevate(?:/(?P<pk>\d+))?/$', CollHistElevate.as_view(), name='collhist_elevate'),
    url(r'^collection/hist/manuscript(?:/(?P<pk>\d+))?/$', CollHistManu.as_view(), name='collhist_manu'),
    url(r'^collection/hist/template(?:/(?P<pk>\d+))?/$', CollHistTemp.as_view(), name='collhist_temp'),
    url(r'^collection/hist/compare(?:/(?P<pk>\d+))?/$', CollHistCompare.as_view(), name='collhist_compare'),
    
    url(r'^basket/sermo/update', BasketUpdate.as_view(), name='basket_update'),
    url(r'^basket/sermo/show', BasketView.as_view(), name='basket_show'),

    url(r'^basket/manu/update', BasketUpdateManu.as_view(), name='basket_update_manu'),
    url(r'^basket/manu/show', BasketViewManu.as_view(), name='basket_show_manu'),

    url(r'^basket/gold/update', BasketUpdateGold.as_view(), name='basket_update_gold'),
    url(r'^basket/gold/show', BasketViewGold.as_view(), name='basket_show_gold'),

    url(r'^basket/super/update', BasketUpdateSuper.as_view(), name='basket_update_super'),
    url(r'^basket/super/show', BasketViewSuper.as_view(), name='basket_show_super'),
    
    url(r'^author/list', AuthorListView.as_view(), name='author_list'),
    url(r'^author/details(?:/(?P<pk>\d+))?/$', AuthorDetails.as_view(), name='author_details'),
    url(r'^author/edit(?:/(?P<pk>\d+))?/$', AuthorEdit.as_view(), name='author_edit'),

    url(r'^report/list', ReportListView.as_view(), name='report_list'),
    url(r'^report/details(?:/(?P<pk>\d+))?/$', ReportDetails.as_view(), name='report_details'),
    url(r'^report/edit(?:/(?P<pk>\d+))?/$', ReportEdit.as_view(), name='report_edit'),
    url(r'^report/download(?:/(?P<pk>\d+))?/$', ReportDownload.as_view(), name='report_results'),

    url(r'^literature/list', LitRefListView.as_view(), name='literature_list'),

    url(r'^keyword/list', KeywordListView.as_view(), name='keyword_list'),
    url(r'^keyword/details(?:/(?P<pk>\d+))?/$', KeywordDetails.as_view(), name='keyword_details'),
    url(r'^keyword/edit(?:/(?P<pk>\d+))?/$', KeywordEdit.as_view(), name='keyword_edit'),

    url(r'^userkeyword/list', UserKeywordListView.as_view(), name='userkeyword_list'),
    url(r'^userkeyword/details(?:/(?P<pk>\d+))?/$', UserKeywordDetails.as_view(), name='userkeyword_details'),
    url(r'^userkeyword/edit(?:/(?P<pk>\d+))?/$', UserKeywordEdit.as_view(), name='userkeyword_edit'),

    url(r'^provenance/list', ProvenanceListView.as_view(), name='provenance_list'),
    url(r'^provenance/details(?:/(?P<pk>\d+))?/$', ProvenanceDetails.as_view(), name='provenance_details'),
    url(r'^provenance/edit(?:/(?P<pk>\d+))?/$', ProvenanceEdit.as_view(), name='provenance_edit'),
    url(r'^provman/details(?:/(?P<pk>\d+))?/$', ProvenanceManDetails.as_view(), name='provenanceman_details'),
    url(r'^provman/edit(?:/(?P<pk>\d+))?/$', ProvenanceManEdit.as_view(), name='provenanceman_edit'),
    url(r'^provcod/details(?:/(?P<pk>\d+))?/$', ProvenanceCodDetails.as_view(), name='provenancecod_details'),
    url(r'^provcod/edit(?:/(?P<pk>\d+))?/$', ProvenanceCodEdit.as_view(), name='provenancecod_edit'),

    url(r'^comment/list', CommentListView.as_view(), name='comment_list'),
    url(r'^comment/details(?:/(?P<pk>\d+))?/$', CommentDetails.as_view(), name='comment_details'),
    url(r'^comment/edit(?:/(?P<pk>\d+))?/$', CommentEdit.as_view(), name='comment_edit'),

    url(r'^bibrange/list', BibRangeListView.as_view(), name='bibrange_list'),
    url(r'^bibrange/details(?:/(?P<pk>\d+))?/$', BibRangeDetails.as_view(), name='bibrange_details'),
    url(r'^bibrange/edit(?:/(?P<pk>\d+))?/$', BibRangeEdit.as_view(), name='bibrange_edit'),

    url(r'^feast/list', FeastListView.as_view(), name='feast_list'),
    url(r'^feast/details(?:/(?P<pk>\d+))?/$', FeastDetails.as_view(), name='feast_details'),
    url(r'^feast/edit(?:/(?P<pk>\d+))?/$', FeastEdit.as_view(), name='feast_edit'),

    url(r'^profile/list', ProfileListView.as_view(), name='profile_list'),
    url(r'^profile/details(?:/(?P<pk>\d+))?/$', ProfileDetails.as_view(), name='profile_details'),
    url(r'^profile/edit(?:/(?P<pk>\d+))?/$', ProfileEdit.as_view(), name='profile_edit'),

    url(r'^project/list', ProjectListView.as_view(), name='project_list'),
    url(r'^project/details(?:/(?P<pk>\d+))?/$', ProjectDetails.as_view(), name='project_details'),
    url(r'^project/edit(?:/(?P<pk>\d+))?/$', ProjectEdit.as_view(), name='project_edit'),

    url(r'^source/list', SourceListView.as_view(), name='source_list'),
    # url(r'^source/details(?:/(?P<pk>\d+))?/$', SourceDetailsView.as_view(), name='source_details'),
    url(r'^source/details(?:/(?P<pk>\d+))?/$', SourceDetails.as_view(), name='source_details'),
    url(r'^source/edit(?:/(?P<pk>\d+))?/$', SourceEdit.as_view(), name='source_edit'),

    url(r'^template/list', TemplateListView.as_view(), name='template_list'),
    url(r'^template/details(?:/(?P<pk>\d+))?/$', TemplateDetails.as_view(), name='template_details'),
    url(r'^template/edit(?:/(?P<pk>\d+))?/$', TemplateEdit.as_view(), name='template_edit'),
    url(r'^template/apply(?:/(?P<pk>\d+))?/$', TemplateApply.as_view(), name='template_apply'),
    url(r'^template/import/$', TemplateImport.as_view(), name='template_import'),

    url(r'^gold/list', SermonGoldListView.as_view(), name='gold_list'),
    url(r'^gold/list', SermonGoldListView.as_view(), name='search_gold'),
    url(r'^gold/details(?:/(?P<pk>\d+))?/$', SermonGoldDetails.as_view(), name='gold_details'),
    url(r'^gold/edit(?:/(?P<pk>\d+))?/$', SermonGoldEdit.as_view(), name='gold_edit'),

    url(r'^dct/list', ResearchSetListView.as_view(), name='researchset_list'),
    url(r'^dct/details(?:/(?P<pk>\d+))?/$', ResearchSetDetails.as_view(), name='researchset_details'),
    url(r'^dct/edit(?:/(?P<pk>\d+))?/$', ResearchSetEdit.as_view(), name='researchset_edit'),
    url(r'^dct/test', passim.dct.views.test_dct, name='test_dct'),

    url(r'^api/countries/$', passim.seeker.views.get_countries, name='api_countries'),
    url(r'^api/cities/$', passim.seeker.views.get_cities, name='api_cities'),
    url(r'^api/libraries/$', passim.seeker.views.get_libraries, name='api_libraries'),
    url(r'^api/origins/$', passim.seeker.views.get_origins, name='api_origins'),
    url(r'^api/locations/$', passim.seeker.views.get_locations, name='api_locations'),
    url(r'^api/litrefs/$', passim.seeker.views.get_litrefs, name='api_litrefs'),
    url(r'^api/litref/$', passim.seeker.views.get_litref, name='api_litref'),
    url(r'^api/sg/$', passim.seeker.views.get_sg, name='api_sg'),
    url(r'^api/sglink/$', passim.seeker.views.get_sglink, name='api_sglink'),
    url(r'^api/ssglink/$', passim.seeker.views.get_ssglink, name='api_ssglink'),
    url(r'^api/ssg2ssg/$', passim.seeker.views.get_ssg2ssg, name='api_ssg2ssg'),
    url(r'^api/ssg/$', passim.seeker.views.get_ssg, name='api_ssg'),
    url(r'^api/ssgdist/$', passim.seeker.views.get_ssgdist, name='api_ssgdist'),
    url(r'^api/sermosig/$', passim.seeker.views.get_sermosig, name='api_sermosig'),
    url(r'^api/manuscripts/$', passim.seeker.views.get_manuscripts, name='api_manuscripts'),
    url(r'^api/authors/list/$', passim.seeker.views.get_authors, name='api_authors'),
    url(r'^api/nicknames/$', passim.seeker.views.get_nicknames, name='api_nicknames'),
    url(r'^api/gldincipits/$', passim.seeker.views.get_gldincipits, name='api_gldincipits'),
    url(r'^api/gldexplicits/$', passim.seeker.views.get_gldexplicits, name='api_gldexplicits'),
    url(r'^api/srmincipits/$', passim.seeker.views.get_srmincipits, name='api_srmincipits'),
    url(r'^api/srmexplicits/$', passim.seeker.views.get_srmexplicits, name='api_srmexplicits'),
    url(r'^api/gldsignatures/$', passim.seeker.views.get_gldsignatures, name='api_gldsignatures'),
    url(r'^api/srmsignatures/$', passim.seeker.views.get_srmsignatures, name='api_srmsignatures'),
    url(r'^api/editions/$', passim.seeker.views.get_editions, name='api_editions'),
    url(r'^api/keywords/$', passim.seeker.views.get_keywords, name='api_keywords'),
    url(r'^api/collections/$', passim.seeker.views.get_collections, name='api_collections'),
    url(r'^api/manuidnos/$', passim.seeker.views.get_manuidnos, name='api_manuidnos'),

    url(r'^api/import/authors/$', passim.seeker.views.import_authors, name='import_authors'),
    url(r'^api/import/gold/$', passim.seeker.views.import_gold, name='import_gold'),
    #url(r'^api/import/ecodex/$', passim.seeker.views.import_ecodex, name='import_ecodex'),
    #url(r'^api/import/ead/$', passim.seeker.views.import_ead, name='import_ead'),

    url(r'^api/import/pdf_lit/$', passim.seeker.views.do_create_pdf_lit, name='create_pdf_lit'), 
    url(r'^api/import/pdf_edi/$', passim.seeker.views.do_create_pdf_edi, name='create_pdf_edi'), 
    url(r'^api/import/pdf_manu/$', passim.seeker.views.do_create_pdf_manu, name='create_pdf_manu'),
     
    url(r'^api/search/ecodex/$', passim.seeker.views.search_ecodex, name='search_ecodex'),
    url(r'^api/gold/get(?:/(?P<pk>\d+))?/$', passim.seeker.views.get_gold, name='get_gold'),
    url(r'^api/comment/send/$', CommentSend.as_view(), name='comment_send'),

    # ================ Any READER APP URLs should come here =======================================
    #url(r'^reader/import/ecodex/$', passim.reader.views.import_ecodex, name='import_ecodex'),
    #url(r'^reader/import/ead/$', passim.reader.views.import_ead, name='import_ead'),
    # ========== NEW method =======================================================================
    url(r'^reader/import/ecodex/$', ReaderEcodex.as_view(), name='import_ecodex'),
    url(r'^reader/import/ead/$', ReaderEad.as_view(), name='import_ead'),
    # =============================================================================================

    # ============== ENRICH STUFF =================================================
    url(r'^enrich/speaker/list', SpeakerListView.as_view(), name='speaker_list'),
    url(r'^enrich/speaker/details(?:/(?P<pk>\d+))?/$', SpeakerDetails.as_view(), name='speaker_details'),
    url(r'^enrich/speaker/edit(?:/(?P<pk>\d+))?/$', SpeakerEdit.as_view(), name='speaker_edit'),

    url(r'^enrich/sentence/list', SentenceListView.as_view(), name='sentence_list'),
    url(r'^enrich/sentence/details(?:/(?P<pk>\d+))?/$', SentenceDetails.as_view(), name='sentence_details'),
    url(r'^enrich/sentence/edit(?:/(?P<pk>\d+))?/$', SentenceEdit.as_view(), name='sentence_edit'),

    url(r'^enrich/unit/list', TestunitListView.as_view(), name='testunit_list'),
    url(r'^enrich/unit/details(?:/(?P<pk>\d+))?/$', TestunitDetails.as_view(), name='testunit_details'),
    url(r'^enrich/unit/edit(?:/(?P<pk>\d+))?/$', TestunitEdit.as_view(), name='testunit_edit'),
    url(r'^enrich/unit/run', TestunitRunView.as_view(), name='testunit_run'),

    url(r'^enrich/set/list', TestsetListView.as_view(), name='testset_list'),
    url(r'^enrich/set/details(?:/(?P<pk>\d+))?/$', TestsetDetails.as_view(), name='testset_details'),
    url(r'^enrich/set/edit(?:/(?P<pk>\d+))?/$', TestsetEdit.as_view(), name='testset_edit'),
    url(r'^enrich/download', TestsetDownload.as_view(), name='testset_results'),
    url(r'^api/enrich/testsets/$', passim.enrich.views.get_testsets, name='api_testsets'),

    # For working with ModelWidgets from the select2 package https://django-select2.readthedocs.io
    url(r'^select2/', include('django_select2.urls')),

    url(r'^definitions$', RedirectView.as_view(url='/'+pfx+'admin/'), name='definitions'),
    url(r'^signup/$', passim.seeker.views.signup, name='signup'),

    url(r'^login/user/(?P<user_id>\w[\w\d_]+)$', passim.seeker.views.login_as_user, name='login_as'),

    url(r'^login/$', LoginView.as_view
        (
            template_name= 'login.html',
            authentication_form= passim.seeker.forms.BootstrapAuthenticationForm,
            extra_context= {'title': 'Log in','year': datetime.now().year,}
        ),
        name='login'),
    url(r'^logout$',  LogoutView.as_view(next_page=reverse_lazy('home')), name='logout'),

    # Uncomment the next line to enable the admin:
    url(r'^admin/', admin.site.urls, name='admin_base'),
]

