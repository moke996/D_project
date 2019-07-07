# -*- coding:utf-8 -*-
from django import forms
from django.core.validators import RegexValidator
from user.models import Users
from django_redis import get_redis_connection

# 创建手机号的正则校验器
mobile_validator = RegexValidator(r"^1[3-9]\d{9}$", "手机号码格式不正确")

class CheckImgCodeForm(forms.Form):
    # 验证长度和是否为空
    mobile = forms.CharField(max_length=11,min_length=11,validators=[mobile_validator],
                             error_messages={
                                 'min_length': '手机号长度有误','max_length': '手机号长度有误',
                                 "required": "手机号不能为空"})
    text = forms.CharField(max_length=4, min_length=4,
                           error_messages={
                               "min_length": "图片验证码错误", "max_length": "图片验证码错误",
                               "required": "图片验证码不能为空"})
    image_code_id = forms.UUIDField(error_messages={"required": "图片UUID不能为空"})

    # 验证其他部分
    def clean(self):
        # super:继承父类方法再重写
        clean_data = super().clean()
        # 获取用户输入的信息
        image_uuid = clean_data.get("image_code_id")
        image_text = clean_data.get("text")
        mobile_num = clean_data.get("mobile")

        # 1.验证手机号是否注册
        if Users.objects.filter(mobile=mobile_num).count():
            raise forms.ValidationError("手机号已注册，请重新输入")
        # 2.输入的验证码与数据库中保存的做校验
        con_redis = get_redis_connection(alias='verify_codes')  # 连接数据库
        img_key = 'img_{}'.format(image_uuid)       # 获得数据库中验证码的键
        redis_img_value = con_redis.get(img_key)    # 获取相应的值(是byte类型)
        # if redis_img_value:
        #     img_value = redis_img_value.decode('utf8')
        # else:
        #     img_value = None
        img_value = redis_img_value.decode('utf8') if redis_img_value else None    # 验证是否拿到
        # con_redis.delete(img_key)               # 取了值就把键(没用了)删掉
        if (not img_value) or (img_value.lower() != image_text.lower()):
            raise forms.ValidationError('图片验证失败！')

        # 检查是否在60s内有发送记录
        sms_tag_name = "sms_tag_{}".format(mobile_num).encode('utf8')
        sms_tag = con_redis.get(sms_tag_name)
        if sms_tag:
            raise forms.ValidationError("获取手机短信验证码过于频繁")
