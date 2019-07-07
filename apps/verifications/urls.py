# -*- coding:utf-8 -*-
from django.urls import path,re_path
from verifications import views

app_name = 'verifications'

urlpatterns = [
    path('image_codes/<uuid:image_code_id>/', views.ImageCode.as_view(), name='image_code'),
    re_path('usernames/(?P<username>\w{6,10})/',views.CheckUsernameView.as_view(), name='check_username'),
    re_path('mobiles/(?P<mobile>1[3-9]\d{9})/',views.CheckMobileView.as_view(), name='check_mobile'),
    re_path('sms_codes/',views.SmsCodesView.as_view(), name='SmsCodes'),

    ]