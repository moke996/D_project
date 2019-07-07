import requests
import logging
from django.shortcuts import render
from django.utils.encoding import escape_uri_path
from django.views import View
from django.conf import settings
from .models import Doc
from django.http import FileResponse,Http404

# 日志器
logger = logging.getLogger('django')



def doc_index(request):
    """渲染文档下载页面"""
    docs = Doc.objects.defer('author','create_time', 'update_time','is_delete').filter(is_delete=False)
    return render(request, 'doc/docDownload.html', locals())


# 文档下载
class DocDownload(View):
    """
    传参：id
    请求方式：GET
    URL:/doc/<int:doc_id>
    流程：id > 从数据库拿到文件地址 > 文件对象 > FileResponse方法返回给用户
    """
    def get(self,request,doc_id):
        # 在数据库中查file_url，获取第一条
        doc = Doc.objects.only('file_url').filter(is_delete=False,id=doc_id).first()
        if doc:
            # 获取文件url并进行路径拼接
            file_url = doc.file_url
            doc_url = settings.SITE_DOMAIN_PORT + file_url
            try:
                # 使用爬虫(requests方法)下载文件对象
                # stream作用：下载大型文件时可以看到下载进度，优化加速
                file = requests.get(doc_url, stream=True)
                # 返回给用户
                res = FileResponse(file)
            except Exception as e:
                logger.info('获取文档内容出现异常:{}'.format(e))
                raise Http404('文件下载异常！')
            # 获取文件类型
            file_type = doc_url.split('.')[-1]
            if not file_type:
                raise Http404('文档url异常！')
            else:
                file_type = file_type.lower()
            # 构造请求头
            if file_type== "pdf":
                res["Content-type"] = "application/pdf"
            elif file_type == "zip":
                res["Content-type"] = "application/zip"
            elif file_type == "doc":
                res["Content-type"] = "application/msword"
            elif file_type == "xls":
                res["Content-type"] = "application/vnd.ms-excel"
            elif file_type == "docx":
                res["Content-type"] = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            elif file_type == "ppt":
                res["Content-type"] = "application/vnd.ms-powerpoint"
            elif file_type == "pptx":
                res["Content-type"] = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            else:
                raise Http404("文档格式不正确！")
            # 对文件名进行转码，用于下载时的显示
            doc_filename = escape_uri_path(doc_url.split('/')[-1])
            # 设置为inline，会直接打开
            # 设置attachment 浏览器才会开始下载
            res["Content-Disposition"] = "attachment; filename*=UTF-8''{}".format(doc_filename)
            return res
        else:
            raise Http404("文档不存在！")




