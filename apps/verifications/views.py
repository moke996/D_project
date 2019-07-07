import logging
import json
import random
import string
from django.shortcuts import render
from django.http import HttpResponse,JsonResponse
from django.views import View
from utils.captcha.captcha import captcha       # 加载验证码模块
from django_redis import get_redis_connection   # 加载redis数据库的方法
from verifications import constants             # 加载常量模块，方便修改
from utils.json_fun import to_json_data         # 引入封装的JsonResponse
from user import models
from utils.user_reg_code import Code,error_map       # 引入错误码
from verifications.forms import CheckImgCodeForm     # 导入form表单(发送短信验证使用)
from utils.yuntongxun.sms import CCP

# 导入日志器
logger = logging.getLogger('django')   # settings里面设置的

# 图片验证码
class ImageCode(View):
    """
     /image_codes/
    """
    def get(self,request,image_code_id):
        # 获取验证码的信息(文本信息和背景图片)
        text,image = captcha.generate_captcha()
        # 连接保存验证码信息的redis数据库verify_codes
        con_redis = get_redis_connection(alias='verify_codes')
        # redis中以键值对形式保存信息
        img_key = 'img_{}'.format(image_code_id)   # 键
        con_redis.setex(img_key, constants.REDIS_IMG_EXPIRES, text)  # (键，过期时间，值)
        # 打印日志(图片验证码)到后台
        logger.info('Image code:{}'.format(text))
        # 指定返回信息和格式
        return HttpResponse(content=image,content_type='image/jpg')

# 用户名验证
class CheckUsernameView(View):
    """
    GET usernames/(?P<username>\w{6,10})/
    """
    def get(self, request, username):
        # 从数据库中统计出该用户名个数
        count = models.Users.objects.filter(username=username).count()
        # 从auth.js知道需要返回的内容是:data.count,data.username
        data = {
            'username': username,
            'count': count
        }
        # return JsonResponse({'data':data}) # 封装到json_fun.py中
        return to_json_data(data=data)

# 手机号验证
class CheckMobileView(View):
    """
    GET mobiles/(?P<mobile>1[3-9]\d{9})/
    """
    def get(self,request, mobile):
        # 从数据库中统计该手机号个数
        count = models.Users.objects.filter(mobile=mobile).count()
        #  从auth.js知道需要返回的内容是:data.count,data.mobile
        data = {
            'mobile': mobile,
            'count': count
        }
        # return JsonResponse({'data': data})  # 封装到json_fun.py中
        return to_json_data(data=data)


# 发送短信验证码
    """
    手机号：不为空，格式正确，没有被注册 
    验证码：不为空，与数据库中保存的做校验
    uuid ：格式是否正确 
    """
class SmsCodesView(View):
    """
    /sms_codes/
    """

    def post(self, request):
        # 1.获取前端发送的参数(是byte类型)
        json_data = request.body
        if not json_data:    # 没获取到就返回错误码
            return to_json_data(errno=Code.PARAMERR, errmsg=error_map[Code.PARAMERR])
        dict_data = json.loads(json_data.decode('utf8')) # 把获取到的json对象转化成字典
        # 2.验证参数 (form表单验证)
        form = CheckImgCodeForm(data=dict_data)
        # 验证信息都正确
        if form.is_valid():
            # 3.保存短信验证码
            mobile = form.cleaned_data.get('mobile')  # 获取用户输入手机号
        # 创建6位随机数的短信验证码内容
            # sms_num = ''
            # for i in range(6):
            #     sms_num += random.choice(string.digits)
            # 创建6位随机数的短信验证码内容
            sms_num = ''.join([random.choice(string.digits) for _ in range(constants.SMS_CODE_NUMS)])
            # 保存到数据库
            con_redis = get_redis_connection(alias='verify_codes')   # 连接redis
            pl = con_redis.pipeline()                     # redis的管道方法（可以两组不同数据一起存入）
            sms_key_name = 'sms_{}'.format(mobile)        # 验证码键名
            sms_tag_name = 'sms_tag_{}'.format(mobile)   # 发送标记健名
            try:
                pl.setex(sms_key_name, constants.SMS_CODE_REDIS_EXPIRES, sms_num)        # (键，过期时间，值)
                pl.setex(sms_tag_name,constants.SEND_SMS_CODE_INTERVAL, 1)
                pl.execute()
            except Exception as e:
                logger.debug("redis 执行错误！".format(e))        # 发送一个日志信息
                return to_json_data(errno=Code.UNKOWNERR,errmsg=error_map[Code.UNKOWNERR])  # 返回错误给前端
            # 4.发送短信验证码(测试)
            logger.info("发送验证码短信[正常][ mobile: %s sms_code: %s]" % (mobile, sms_num))
            return to_json_data(errno=Code.OK, errmsg="短信验证码发送成功")
            # 发送短信
            # try:
            #     result = CCP().send_template_sms(mobile,   # 手机号
            #                                      [sms_num, constants.SMS_CODE_REDIS_EXPIRES], # [验证码内容，有效期]
            #                                      constants.SMS_CODE_TEMP_ID) # 短信模板id
            # except Exception as e:
            #     logger.error("发送验证码短信[异常][ mobile: %s, message: %s ]" % (mobile, e))
            #     return to_json_data(errno=Code.SMSERROR, errmsg=error_map[Code.SMSERROR])
            # else:
            #     if result == 0:       # 0：发送成功标志（具体查看sms.py）
            #         logger.info("发送验证码短信[正常][ mobile: %s sms_code: %s]" % (mobile, sms_num))
            #         return to_json_data(errno=Code.OK, errmsg="短信验证码发送成功")
            #     else:
            #         logger.warning("发送验证码短信[失败][ mobile: %s ]" % mobile)
            #         return to_json_data(errno=Code.SMSFAIL, errmsg=error_map[Code.SMSFAIL])
        # 5.返回给前端
        else:
            # 定义一个错误信息列表
            err_msg_list = []
            for item in form.errors.get_json_data().values():
                err_msg_list.append(item[0].get('message'))
            err_msg_str = '/'.join(err_msg_list)  # 拼接错误信息为一个字符串

            return to_json_data(errno=Code.PARAMERR, errmsg=err_msg_str)

