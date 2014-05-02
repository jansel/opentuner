from django.conf.urls import patterns, include, url

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
import views.charts
admin.autodiscover()

urlpatterns = patterns('',
    # Examples:
    # url(r'^$', 'stats_app.views.home', name='home'),
    # url(r'^stats_app/', include('stats_app.foo.urls')),

    # Uncomment the admin/doc line below to enable admin documentation:
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    url(r'^admin/', include(admin.site.urls)),
    url(r'^graph.png$', views.charts.display_graph, name='graph'),
    url(r'^$', views.charts.display_full_page, name='graph_page'),
)
