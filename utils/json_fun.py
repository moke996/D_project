# # -*- coding:utf-8 -*-
from django.http import JsonResponse
from utils.user_reg_code import Code


def to_json_data(errno=Code.OK, errmsg='', data=None, **kwargs):
    json_dict = {'errno': errno, 'errmsg': errmsg, 'data': data}
    # kwargs是字典类型
    # 判断kwargs是否存在，是不是字典，是不是空字典
    if kwargs and isinstance(kwargs, dict) and kwargs.keys():
        # 更合并成一个新字典）
        json_dict.update(kwargs)

    return JsonResponse(json_dict)