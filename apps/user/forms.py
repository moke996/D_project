# -*- coding:utf-8 -*-
import re
from django import forms

from django.db.models import Q
from django.contrib.auth import login
from django_redis import get_redis_connection
from verifications.constants import SMS_CODE_NUMS
from .models import Users
from user import constant


class RegisterForm(forms.Form):
    """
    点击立即注册需要验证的字段
    """
    username = forms.CharField(label='用户名', max_length=20, min_length=5,
                               error_messages={"min_length": "用户名长度要大于5", "max_length": "用户名长度要小于20",
                                               "required": "用户名不能为空"}
                               )
    password = forms.CharField(label='密码', max_length=20, min_length=6,
                               error_messages={"min_length": "密码长度要大于6", "max_length": "密码长度要小于20",
                                               "required": "密码不能为空"}
                               )
    password_repeat = forms.CharField(label='确认密码', max_length=20, min_length=6,
                                      error_messages={"min_length": "密码长度要大于6", "max_length": "密码长度要小于20",
                                                      "required": "密码不能为空"}
                                      )
    mobile = forms.CharField(label='手机号', max_length=11, min_length=11,
                             error_messages={"min_length": "手机号长度有误", "max_length": "手机号长度有误",
                                             "required": "手机号不能为空"})

    sms_code = forms.CharField(label='短信验证码', max_length=SMS_CODE_NUMS, min_length=SMS_CODE_NUMS,
                               error_messages={"min_length": "短信验证码长度有误", "max_length": "短信验证码长度有误",
                                               "required": "短信验证码不能为空"})

    def clean_mobile(self):
        """手机号校验"""
        tel = self.cleaned_data.get('mobile')
        if not re.match(r"^1[3-9]\d{9}$", tel):
            raise forms.ValidationError("手机号码格式不正确")
        if Users.objects.filter(mobile=tel).exists():
            raise forms.ValidationError("手机号已注册，请重新输入！")
        return tel

    def clean(self):
        """
        短信验证码校验
        """
        cleaned_data = super().clean()
        passwd = cleaned_data.get('password')
        passwd_repeat = cleaned_data.get('password_repeat')

        if passwd != passwd_repeat:
            raise forms.ValidationError("两次密码不一致")

        # 拿到用户输入手机号（拼接键名用）
        tel = cleaned_data.get('mobile')
        # 拿到用户输入短信验证码
        sms_text = cleaned_data.get('sms_code')
        # 建立redis连接
        redis_conn = get_redis_connection(alias='verify_codes')
        # 拼接短信验证码键名
        sms_fmt = "sms_{}".format(tel)
        # 获取数据库中的短信验证码
        real_sms = redis_conn.get(sms_fmt)
        # 校验
        if (not real_sms) or (sms_text != real_sms.decode('utf-8')):
            raise forms.ValidationError("短信验证码错误")



class LoginForm(forms.Form):
    """
    验证登录账号，密码格式
    """
    # 命名是看js文件传递的什么参数
    user_account = forms.CharField()
    password = forms.CharField(label='密码', max_length=20, min_length=6,
                               error_messages={"min_length": "密码长度要大于6", "max_length": "密码长度要小于20",
                                               "required": "密码不能为空"}
                               )
    remember_me = forms.BooleanField(required=False)  # 看js文件

    def __init__(self,*args,**kwargs):
        self.request = kwargs.pop('request', None)    # 用pop方法获取
        super().__init__(*args, **kwargs)             # 重写，新增了self.request属性


    def clean_user_account(self):
        """登录账号可以是用户名，也可以是密码，需要单独验证"""
        user_info = self.cleaned_data.get('user_account')
        if not user_info:
            raise forms.ValidationError('登录账号不能为空')
        # 验证登录账号类型(不是手机号，也不是用户名)
        if (not re.match(r"^1[3-9]\d{9}$", user_info)) and (len(user_info)<5 or len(user_info)>20):
            raise forms.ValidationError("账号格式不正确")
        # 不满足上面条件即为输入正确
        return user_info

    def clean(self):
        """联合校验"""
        cleaned_data = super().clean()
        login_name = cleaned_data.get('user_account')
        passwd = cleaned_data.get('password')
        hode_login = cleaned_data.get('remember_me')

        # 数据库中查询(Q联合查询)
        user_queryset = Users.objects.filter(Q(username=login_name) | Q(mobile=login_name))  # 登录账号是用户名或者密码
        if user_queryset:
            user = user_queryset.first()
            if user.check_password(passwd):   # check方法自动查询用户对应密码
                # 登录操作
                if not hode_login:   # 没有勾选记住
                    self.request.session.set_expiry(None)   # None:默认时长过期,0:关闭页面过期
                else:
                    self.request.session.set_expiry(constant.USER_SESSION_EXPIRES)
                # login(request,用户实例)
                login(self.request, user)
            else:
                raise forms.ValidationError('密码不正确，请重新输入')
        else:
            raise forms.ValidationError('登录账号不存在，请重新输入！')







