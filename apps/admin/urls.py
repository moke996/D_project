# -*- coding:utf-8 -*-

from django.urls import path
from admin import views


app_name = 'admin'

urlpatterns = [
    path('', views.IndexView.as_view(), name='index'),
    path('tags/', views.TagManageView.as_view(), name='tags'),
    path('tags/<tag_id>/', views.TagEditView.as_view(), name='tag_edit'),

    path('hotnews/', views.HotNewsManage.as_view(), name='hotnews'),
    path('hotnews/<int:hotnews_id>/', views.HotNewsEdit.as_view(), name='hotnews_ID'),
    path('hotnews/add/', views.HotNewsAdd.as_view(), name='hotnews_add'),
    path('tags/<int:tag_id>/news/', views.NewsByTagID.as_view(), name='news_by_tagid'),

    path('news/',views.NewsManage.as_view(),name='news_manage'),
    path('news/<int:news_id>/',views.NewsEditView.as_view(),name='news_edit'),
    path('news/pub/',views.NewsPubView.as_view(),name='news_pub'),

    path('news/images/',views.NewsUploadImage.as_view(),name='upload_image'),
    path('token/',views.UploadToken.as_view(),name='upload_token'),
    path('markdown/images/',views.MarkDownUploadImage.as_view(),name='markdown_image_upload'),

    path('docs/', views.DocsManageView.as_view(), name='docs_manage'),
    path('docs/<int:doc_id>/', views.DocEditView.as_view(), name='docs_edit'),
    path('docs/files/', views.DocUploadFile.as_view(), name='upload_file'),
    path('docs/pub/', views.DocsPubView.as_view(), name='doc_pub'),

    path('courses/', views.CoursesManageView.as_view(), name='courses_manage'),
    path('courses/<int:course_id>/', views.CourseEditView.as_view(), name='courses_edit'),
    path('courses/pub/', views.CoursePubView.as_view(), name='courses_pub'),

    path('banners/', views.BannerManageView.as_view(), name='banners_manage'),
    path('banners/<int:banner_id>/', views.BannerEditView.as_view(), name='banners_edit'),
    path('banners/add/', views.BannerAddView.as_view(), name='banners_add'),

    path('groups/',views.GroupManageView.as_view(), name='group_manage'),
    path('groups/<int:group_id>/', views.GroupEditView.as_view(), name='group_edit'),
    path('groups/add/', views.GroupAddView.as_view(), name='group_add'),

    path('users/', views.UsersManageView.as_view(), name='users_manage'),
    path('users/<int:user_id>/', views.UsersEditView.as_view(), name='users_edit'),

]