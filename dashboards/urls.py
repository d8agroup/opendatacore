from django.conf.urls.defaults import patterns, url
from dashboards.views import *

urlpatterns = patterns('',
    url(r'(\w+)', redirect_to_dashboard),
)