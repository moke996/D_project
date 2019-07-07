import json
import logging
import qiniu

from django.contrib.auth.mixins import LoginRequiredMixin,PermissionRequiredMixin
from django.http import JsonResponse, Http404
from datetime import datetime
from django.contrib.auth.models import Group,Permission
from django.core.paginator import Paginator, EmptyPage
from django.db.models import Count
from django.shortcuts import render
from django.views import View
from D_project import settings

from news import models
from doc.models import Doc
from user.models import Users
from course.models import Course,CourseCategory,Teacher

from urllib.parse import urlencode
from utils.secrets import qiniu_secret_info
from utils.json_fun import to_json_data
from utils.user_reg_code import Code, error_map
from utils import paginator_script
from utils.fastdfs.fdfs import FDFS_Client
from . import forms
from . import constants


logger = logging.getLogger('django')



# 后台管理首页
class IndexView(LoginRequiredMixin,View):
    """渲染出后台首页"""
    # 权限设置
    login_url = 'user:login'      # 想进入后台，必须先登录
    redirect_field_name = 'next'   # 登录后跳转到相应页面
    # 页面渲染
    def get(self,request):
        return render(request, 'admin/index/index.html')

# 标签管理页
class TagManageView(PermissionRequiredMixin,View):
    """
    URL：/admin/tags/
    """
    # 权限设置
    permission_required = ('news:add_tag','news:view_tag')
    raise_exception = True
    def handle_no_permission(self):
        if self.request.method.lower() != 'get':                       # 有两种请求方式，所以要判断
            return to_json_data(errno=Code.ROLEERR, errmsg='没有操作权限')
        else:
            return super(TagManageView, self).handle_no_permission()

    # 页面渲染( 返回：tag_name,news_num)
    def get(self,request):
        # 查询tag表中id,name两字段，以news表中每个tag_id对应的news数量分组(value查询返回字典)
        tags = models.Tag.objects.select_related('news').\
            values('id', 'name').annotate(num_news=Count('news')).\
            filter(is_delete=False).order_by('-num_news')

        return render(request,'admin/news/tag_manage.html', locals())

    # 添加标签
    def post(self,request):
        # 1.获取参数
        json_data = request.body
        if not json_data:
            return to_json_data(errno=Code.PARAMERR, errmsg=error_map[Code.PARAMERR])
        # 把获取到的json对象转化成字典
        dict_data = json.loads(json_data.decode('utf8'))
        # 前端传来的新的tag_name
        tag_name = dict_data.get('name')
        if tag_name:
            # 去标签名两边空格
            tag_name = tag_name.strip()
            # 查询数据库中无则增，查询返回结果是含有两个参数的元组(tag_instance,tag_boolean)
            tag_tuple = models.Tag.objects.get_or_create(name=tag_name)   # create返回True或False
            # 返回的两个参数分别赋给新的值
            tag_instance, tag_boolean = tag_tuple
            #  判断是创建还是已经存在的
            if tag_boolean == True:
                news_tag ={
                    'id': tag_instance.id,
                    'name': tag_instance.name
                }
                return to_json_data(errmsg="标签创建成功",data=news_tag)
            else:
                return to_json_data(errno=Code.DATAEXIST,errmsg="标签已存在")
        else:
            return to_json_data(errno=Code.DATAEXIST,errmsg="标签不能为空")

# 对标签的操作
class TagEditView(PermissionRequiredMixin,View):
    """
    URL:/admin/tags/<tag_id>/
    """
    # 权限设置
    permission_required = ('news.delete_tag', 'news.change_tag')
    raise_exception = True
    # 删除，编辑返回的是to_json_data，所以要从写返回信息
    def handle_no_permission(self):
        return to_json_data(errno=Code.ROLEERR, errmsg='没有操作权限')

    # 删除标签
    def delete(self, request, tag_id):
        tag = models.Tag.objects.only('id').filter(id=tag_id).first()
        if tag:
            tag.is_delete = True
            tag.save(update_fields=['is_delete'])     # 优化保存(只更新发生变化的)
            return to_json_data(errmsg="标签删除成功！")
        else:
            return to_json_data(errno=Code.PARAMERR, errmsg="标签不存在！")

    # 编辑标签
    def put(self,request,tag_id):
        # 1.获取参数
        json_data = request.body
        if not json_data:
            return to_json_data(errno=Code.PARAMERR, errmsg=error_map[Code.PARAMERR])
        # 把获取到的json对象转化成字典
        dict_data = json.loads(json_data.decode('utf8'))
        # 前端传来的修改后的tag_name
        tag_name = dict_data.get('name')
        print(type(tag_name))

        # 2.从数据库拿到修改前的tag对象
        tag = models.Tag.objects.only('name').filter(id=tag_id).first()
        if tag:
            # 去标签名两边空格
            tag_name = tag_name.strip()
            # 查询修改后的tag_name是否已经存在
            if not models.Tag.objects.only('id').filter(name=tag_name).exists():
                # 验证标签名是否变化
                if tag.name == tag_name:
                    return to_json_data(errno=Code.PARAMERR, errmsg="标签名未变化！")
                else:
                    tag.name = tag_name
                    tag.save(update_fields=['name'])        # 优化保存
                    return to_json_data(errmsg="标签更新成功！")
            else:
                return to_json_data(errno=Code.PARAMERR, errmsg="标签名已存在！")
        else:
            return to_json_data(errno=Code.PARAMERR, errmsg="标签不存在！")




# 热门文章管理
class HotNewsManage(PermissionRequiredMixin,View):
    """
    URL:/admin/hotnews/
    """
    # 权限设置 (get方法返回了一个页面，所以不用重写)
    permission_required = ('news.view_hotnews')
    raise_exception = True

    # 页面渲染
    def get(self,request):
        # 参数：news_title,news_id,tag_name,优先级
        hot_news = models.HotNews.objects.select_related('news__tag').\
            only('news__title','news__tag__name','priority','news_id').filter(is_delete=False).\
            order_by('priority','-news__clicks')[:constants.SHOW_HOTNEWS_COUNT]
        return render(request,'admin/news/news_hot.html',locals())

# 对热门文章的标签操作
class HotNewsEdit(PermissionRequiredMixin,View):
    """
    URL:/admin/hotnews/<int:hotnews_id>/
    """
    # 权限设置
    permission_required = ('news.delete_hotnews', 'news.change_hotnews')
    raise_exception = True
    # 删除，编辑返回的是to_json_data，所以要从写返回信息
    def handle_no_permission(self):
        return to_json_data(errno=Code.ROLEERR, errmsg='没有操作权限')

    # 删除
    def delete(self,request,hotnews_id):
        hotnews = models.HotNews.objects.only('id').filter(id=hotnews_id).first()
        if hotnews:
            hotnews.is_delete = True
            hotnews.save(update_fields=['is_delete'])  # 优化保存(只更新发生变化的)
            return to_json_data(errmsg="热门新闻删除成功！")
        else:
            return to_json_data(errno=Code.PARAMERR, errmsg="该新闻不存在！")

    # 编辑
    def put(self,request,hotnews_id):
        """更新热门新闻优先级"""
        # 1.获取参数
        json_data = request.body
        if not json_data:
            return to_json_data(errno=Code.PARAMERR, errmsg=error_map[Code.PARAMERR])
        # 把获取到的json对象转化成字典
        dict_data = json.loads(json_data.decode('utf8'))

        try:
            priority = int(dict_data.get('priority'))    # 字符串转换
            priority_list = [i for i,_ in models.HotNews.PTL_CHOICES]       # 使用了列表生成式只拿i,不需要的用_代替
            if priority not in priority_list:
                return to_json_data(errno=Code.PARAMERR, errmsg='热门文章优先级设置错误!')
        except Exception as e:
            logger.info('热门文章优先级异常:\n{}'.format(e))
            return to_json_data(errno=Code.PARAMERR, errmsg='热门文章优先级设置错误!')
        # 2.和数据库中的对比
        hotnews = models.HotNews.objects.only('id').filter(id=hotnews_id).first()
        # 3.校验，返回
        if not hotnews:
            return to_json_data(errno=Code.PARAMERR, errmsg='需要更新的热门文章不存在!')
        else:
            if hotnews.priority == priority:
                return to_json_data(errno=Code.PARAMERR, errmsg='优先级未改变!')
            else:
                hotnews.priority = priority
                hotnews.save(update_fields=['priority'])
                return to_json_data(errmsg='优先级!')

# 添加文章页
class HotNewsAdd(PermissionRequiredMixin,View):
    """
    URL:/admin/hotnews/add/
    """
    # 权限设置
    permission_required = ('news.view_hotnews', 'news.add_hotnews')
    raise_exception = True
    def handle_no_permission(self):
        if self.request.method.lower() != 'get':                # 有两种请求方式，所以要判断
            return to_json_data(errno=Code.ROLEERR, errmsg='没有操作权限')
        else:
            return super(HotNewsAdd, self).handle_no_permission()

    # 添加页面渲染
    def get(self,request):
        # 查询tag表中id,name两字段，以news表中每个tag_id对应的数量分组(value查询返回字典)
        tags = models.Tag.objects.values('id', 'name').annotate(num_news=Count('news')).\
            filter(is_delete=False).order_by('num_news')
        priority_dict = dict(models.HotNews.PTL_CHOICES)         # 元祖转字典
        return  render(request,'admin/news/news_hot_add.html',locals())

    # 添加后保存
    def post(self,request):
        """ 只需要两个参数：news_id,优先级 """
        # 1.获取参数
        json_data = request.body
        if not json_data:
            return to_json_data(errno=Code.PARAMERR, errmsg=error_map[Code.PARAMERR])
        dict_data = json.loads(json_data.decode('utf8'))     # 把获取到的json对象转化成字典

        # news_id的验证
        try:
            news_id = int(dict_data.get('news_id'))
        except Exception as e:
            logger.info('热门文章:\n{}'.format(e))
            return to_json_data(errno=Code.PARAMERR, errmsg='参数错误')
        if not models.News.objects.filter(id=news_id).exists():
            return to_json_data(errno=Code.PARAMERR, errmsg='文章不存在')

        # 优先级的验证
        try:
            priority = int(dict_data.get('priority'))
            priority_list = [i for i, _ in models.HotNews.PTL_CHOICES]
            if priority not in priority_list:
                return to_json_data(errno=Code.PARAMERR, errmsg='优先级设置错误')
        except Exception as e:
            logger.info('热门文章优先级异常：\n{}'.format(e))
            return to_json_data(errno=Code.PARAMERR, errmsg='优先级设置错误')

        # 存数据库中
        hotnews_tuple = models.HotNews.objects.get_or_create(news_id=news_id)
        hotnews, is_created = hotnews_tuple
        hotnews.priority = priority  # 修改优先级
        hotnews.save(update_fields=['priority'])
        return to_json_data(errmsg="热门文章创建成功")

# 添加文章之文章分类
class NewsByTagID(PermissionRequiredMixin,View):
    """
    URL:/admin/tags/<int:tag_id>/news
    """
    # 权限设置
    permission_required = ('news.view_news')
    raise_exception = True
    def handle_no_permission(self):
        return to_json_data(errno=Code.ROLEERR, errmsg='没有操作权限')

    # 页面渲染
    def get(self,request,tag_id):
        news = models.News.objects.filter(is_delete=False, tag_id=tag_id).values('id','title')
        news_list = [i for i in news]    # 列表嵌套字典
        return to_json_data(data={'news': news_list})



# 文章管理
class NewsManage(PermissionRequiredMixin,View):
    """
    URL:/admin/news/
    请求参数：？start_time=&end_time=&title=&author_name=&tag_id=
    返回参数：news_title,author_username,tag_name,update_name,id
    """
    # 权限设置
    permission_required = ('news.view_news')
    raise_exception = True

    # 页面渲染
    def get(self,request):
        # 前端没有传参时显示的信息
        tags = models.Tag.objects.only('id','name').filter(is_delete=False)
        newses = models.News.objects.select_related('author','tag').\
            only('title','author__username','tag__name','update_time').filter(is_delete=False)
        # 前端传递了参数
        # 1.通过时间过滤
        try:
            # 获取查询起始时间
            start_time = request.GET.get('start_time','')
            # 对时间格式化
            start_time = datetime.strftime(start_time,'%Y/%m/%d') if start_time else ''
            # 获取查询截止时间
            end_time = request.GET.get('end_time','')
            # 时间格式化
            end_time = datetime.strftime(end_time,'%Y/%m/%d') if end_time else ''
        except Exception as e:
            logger.info("用户输入时间有误：\n{}".format(e))
            start_time = end_time = ''

        # 查询条件：有起始时间无截止时间
        if start_time and not end_time:
            # 对news继续查询(__gte:大于等于)
            newses = newses.filter(update_time__gte=start_time)

        # 查询条件：有截止时间无起始时间
        if end_time and not start_time:
            # 对news继续查询(__ite:小于等于)
            newses = newses.filter(update_time__ite=end_time)

        # 查询条件：有起始时间有结束时间
        if start_time and end_time:
            # 对news继续查询(__range:范围)
            newses = newses.filter(update_time__range=(start_time,end_time))

        # 通过title过滤
        title = request.GET.get('title','')
        if title:
            newses = newses.filter(title__icontains=title)     # icontains：不区分大小写

        # 通过作者查询
        author_name = request.GET.get('author_name','')
        if author_name:
            newses = newses.filter(author__username__icontains=author_name)

        # 通过tag_id进行过滤
        try:
            tag_id = int(request.GET.get('tag_id',0))
        except Exception as e:
            logger.info("标签错误：\n".format(e))
            tag_id=0
        # id存在但是没有对应news时，返回0
        if tag_id:
            newses = newses.filter(tag_id=tag_id)
        # id存在但是没有对应news时，返回当前页面
        # if tag_id:
        # news = news.filter(is_delete=False, tag_id=tag_id) or \
        #          news.filter(is_delete=False)

        # 获取第几页内容
        try:
            # 获取前端的页码,默认是第一页
            page = int(request.GET.get('page', 1))
        except Exception as e:
            logger.info("当前页数错误：\n{}".format(e))
            page = 1
        paginator = Paginator(newses, constants.PER_PAGE_NEWS_COUNT)
        try:
            news_info = paginator.page(page)
        except EmptyPage:
            # 若用户访问的页数大于实际页数，则返回最后一页数据
            logging.info("用户访问的页数大于总页数。")
            news_info = paginator.page(paginator.num_pages)

        # 分页功能
        paginator_data = paginator_script.get_paginator_data(paginator, news_info)

        # 时间格式再转成字符串格式
        start_time = start_time.strftime('%Y/%m/%d') if start_time else ''
        end_time = end_time.strftime('%Y/%m/%d') if end_time else ''

        # 返回给前端
        context = {
            'news_info': news_info,
            'tags': tags,
            'start_time': start_time,
            "end_time": end_time,
            "title": title,
            "author_name": author_name,
            "tag_id": tag_id,
            "other_param": urlencode({
                "start_time": start_time,
                "end_time": end_time,
                "title": title,
                "author_name": author_name,
                "tag_id": tag_id,
            })
        }
        context.update(paginator_data)
        return render(request, 'admin/news/news_manage.html', context=context)

# 文章管理之编辑、删除操作
class NewsEditView(PermissionRequiredMixin,View):
    """
    URL:/admin/news/<int:news_id>/
    """
    # 权限修改
    permission_required = ('news.delete_news', 'news.change_news', 'news.view_news')
    raise_exception = True
    def handle_no_permission(self):
        if self.request.method.lower() != 'get':
            return to_json_data(errno=Code.ROLEERR, errmsg='没有操作权限')
        else:
            return super(NewsEditView, self).handle_no_permission()

    # 删除
    def delete(self,request,news_id):
        # 从前端直接获取news_id和数据库查到的id做校验
        news = models.News.objects.only('id').filter(id=news_id).first()
        if news:
            news.is_delete = True
            news.save(update_fields=['is_delete'])
            return to_json_data(errmsg='文章删除成功!')
        else:
            return to_json_data(errno=Code.PARAMERR, errmsg="该文章不存在！")

    # 编辑
    def get(self,request,news_id):
        # 查id=news_id的文章的所有字段
        news = models.News.objects.filter(id=news_id).first()
        if news:
            # 编辑页面还需要返回所有的tag_name
            tags = models.Tag.objects.only('id', 'name').filter(is_delete=False)
            return render(request,'admin/news/news_pub.html',locals())
        else:
            return to_json_data(errno=Code.PARAMERR, errmsg="该文章不存在！")

    # 文章更新接口
    def put(self,request,news_id):
        news = models.News.objects.filter(id=news_id).first()
        if news:
            # 1.获取前端参数
            json_data = request.body
            if not json_data:
                return to_json_data(errno=Code.PARAMERR, errmsg=error_map[Code.PARAMERR])
            dict_data = json.loads(json_data.decode('utf8'))   # 把获取到的json对象转化成字典
            # 2.form表单验证
            form = forms.NewsPubForm(data=dict_data)
            if form.is_valid():
                # 3.保存到数据库
                news.title = form.cleaned_data.get('title')
                news.digest = form.cleaned_data.get('digest')
                news.content = form.cleaned_data.get('content')
                news.image_url = form.cleaned_data.get('image_url')
                news.tag = form.cleaned_data.get('tag')
                news.save()
                return to_json_data(errmsg="文章更新成功！")
            else:
                # 定义一个错误信息列表
                err_msg_list = []
                for item in form.errors.get_json_data().values():
                    err_msg_list.append(item[0].get('message'))
                err_msg_str = '/'.join(err_msg_list)  # 拼接错误信息为一个字符串
                return to_json_data(errno=Code.PARAMERR, errmsg=err_msg_str)
        else:
            return to_json_data(errno=Code.PARAMERR, errmsg="该文章不存在！")

# 文章发布
class NewsPubView(PermissionRequiredMixin,View):
    """
    URL:/admin/news/pub
    """
    # 权限修改
    permission_required = ('news.view_news', 'news.add_news')
    raise_exception = True
    def handle_no_permission(self):
        if self.request.method.lower() != 'get':
            return to_json_data(errno=Code.ROLEERR, errmsg='没有操作权限')
        else:
            return super(NewsPubView, self).handle_no_permission()

    # 页面渲染
    def get(self,request):
        tags = models.Tag.objects.only('id','name').filter(is_delete=False)
        return render(request,'admin/news/news_pub.html',locals())

    # 文章发布接口
    def post(self,request):
        # 1.获取前端参数
        json_data = request.body
        if not json_data:
            return to_json_data(errno=Code.PARAMERR, errmsg=error_map[Code.PARAMERR])
        dict_data = json.loads(json_data.decode('utf8'))  # 把获取到的json对象转化成字典
        # 2.form表单验证
        form = forms.NewsPubForm(data=dict_data)
        if form.is_valid():
            # 3.保存到数据库
            news_instance = form.save(commit=False)      # 先缓存(因为form表单只有五个参数)
            news_instance.author = request.user          # 给文章添加作者信息
            news_instance.save()
            return to_json_data(errmsg="文章发布成功！")
        else:
            # 定义一个错误信息列表
            err_msg_list = []
            for item in form.errors.get_json_data().values():
                err_msg_list.append(item[0].get('message'))
            err_msg_str = '/'.join(err_msg_list)  # 拼接错误信息为一个字符串
            return to_json_data(errno=Code.PARAMERR, errmsg=err_msg_str)

# 文章发布之本地上传
class NewsUploadImage(View):
    """
    URL:/admin/news/images/
    """
    def post(self,request):
        # 1.获取图片文件对象
        image_file = request.FILES.get('image_file')
        # 是否拿到
        if not image_file:
            return to_json_data(errno=Code.PARAMERR, errmsg='从前端获取图片失败')
        # 校验文件类型
        if image_file.content_type not in ('image/jpeg', 'image/png', 'image/gif'):
            return to_json_data(errno=Code.DATAERR, errmsg='不能上传非图片文件')
        # 获取文件后缀名
        try:
            image_ext_name = image_file.name.split(".")[-1]
        except Exception as e:
            logger.info('图片拓展名异常：{}'.format(e))
            image_ext_name = 'jpg'
        # 2.上传文件对象
        try:
            upload_res = FDFS_Client.upload_by_buffer(image_file.read(), file_ext_name=image_ext_name)
        except Exception as e:
            logger.error('图片上传出现异常：{}'.format(e))
            return to_json_data(errno=Code.UNKOWNERR, errmsg='图片上传异常')
        # except没有捕获异常时执行else
        else:
            if upload_res.get('Status') != 'Upload successed.':
                logger.info('图片上传到FastDFS服务器失败')
                return to_json_data(Code.UNKOWNERR, errmsg='图片上传到服务器失败')
            else:
                image_name = upload_res.get('Remote file_id')
                image_url = settings.FASTDFS_SERVER_DOMAIN + image_name
                return to_json_data(data={'image_url': image_url}, errmsg='图片上传成功')

# 文章发布之上传七牛云
class UploadToken(View):
    """
    URL:/admin/token/
    """
    def get(self, request):
        # 引用七牛云的ak,sk和储存空间(d_project)
        access_key = qiniu_secret_info.QI_NIU_ACCESS_KEY
        secret_key = qiniu_secret_info.QI_NIU_SECRET_KEY
        bucket_name = qiniu_secret_info.QI_NIU_BUCKET_NAME
        # 构建链接对象
        q = qiniu.Auth(access_key, secret_key)
        # 往q对象中传入bucket_name(你的存储空间)
        token = q.upload_token(bucket_name)
        return JsonResponse({"uptoken": token})

# 文章发布之副文本图片上传
from django.utils.decorators import method_decorator    # 类装饰器
from  django.views.decorators.csrf import csrf_exempt   # 函数装饰器
@method_decorator(csrf_exempt,name='dispatch')          # dispatch:代表类里面所有函数都被装饰
class MarkDownUploadImage(View):
    """
    URL：/admin/markdown/images/
    """
    def post(self, request):
        # 1.获取图片文件对象
        image_file = request.FILES.get('editormd-image-file')
        # 校验是否拿到
        if not image_file:
            logger.info('从前端获取图片失败')
            return JsonResponse({'success': 0, 'message': '从前端获取图片失败'})
        # 校验图片格式
        if image_file.content_type not in ('image/jpeg', 'image/png', 'image/gif'):
            return JsonResponse({'success': 0, 'message': '不能上传非图片文件'})
        # 获取文件后缀名
        try:
            image_ext_name = image_file.name.split('.')[-1]
        except Exception as e:
            logger.info('图片拓展名异常：{}'.format(e))
            image_ext_name = 'jpg'
        # 2.上传文件对象
        try:
            upload_res = FDFS_Client.upload_by_buffer(image_file.read(), file_ext_name=image_ext_name)
        except Exception as e:
            logger.error('图片上传出现异常：{}'.format(e))
            return JsonResponse({'success': 0, 'message': '图片上传异常'})
        else:
            if upload_res.get('Status') != 'Upload successed.':
                logger.info('图片上传到FastDFS服务器失败')
                return JsonResponse({'success': 0, 'message': '图片上传到服务器失败'})
            else:
                image_name = upload_res.get('Remote file_id')
                image_url = settings.FASTDFS_SERVER_DOMAIN + image_name
                return JsonResponse({'success': 1, 'message': '图片上传成功', 'url': image_url})



# 文档管理
class DocsManageView(PermissionRequiredMixin,View):
    """
    URL：/admin/docs/
    """
    # 权限设置
    permission_required = ('doc.view_doc')
    raise_exception = True

    # 文档管理页面渲染
    def get(self,request):
        docs = Doc.objects.only('title', 'update_time').filter(is_delete=False)
        return render(request, 'admin/doc/docs_manage.html', locals())

# 文档管理之编辑、删除操作
class DocEditView(PermissionRequiredMixin,View):
    """
    URL:/admin/docs/<int:doc_id>
    """
    # 权限设置
    permission_required = ('doc.view_doc', 'doc.delete_doc', 'doc.change_doc')
    raise_exception = True
    def handle_no_permission(self):
        if self.request.method.lower() != 'get':
            return to_json_data(errno=Code.ROLEERR, errmsg='没有操作权限')
        else:
            return super(DocEditView, self).handle_no_permission()

    # 删除
    def delete(self,request,doc_id):
        doc = Doc.objects.filter(is_delete=False, id=doc_id).first()
        if doc:
            doc.is_delete = True
            doc.save(update_fields=['is_delete', 'update_time'])
            return to_json_data(errmsg="文档删除成功")
        else:
            return to_json_data(errno=Code.NODATA, errmsg='需要删除的文档不存在')

    # 编辑
    def get(self,request,doc_id):
        doc = Doc.objects.filter(id=doc_id).first()
        if doc:
            return render(request, 'admin/doc/docs_pub.html', locals())
        else:
            return to_json_data(errno=Code.NODATA, errmsg='该文档不存在')

    # 更新接口
    def put(self,request,doc_id):
        doc = Doc.objects.filter(id=doc_id).first()
        if doc:
            # 1.获取前端参数
            json_data = request.body
            if not json_data:
                return to_json_data(errno=Code.PARAMERR, errmsg=error_map[Code.PARAMERR])
            dict_data = json.loads(json_data.decode('utf8'))  # 把获取到的json对象转化成字典
            # 2.form表单验证
            form = forms.DocsPubForm(data=dict_data)
            if form.is_valid():
                # 3.保存到数据库
                for key,value in form.cleaned_data.items():
                    setattr(doc,key,value)
                doc.save()
                return to_json_data(errmsg="文档更新成功！")
            else:
                # 定义一个错误信息列表
                err_msg_list = []
                for item in form.errors.get_json_data().values():
                    err_msg_list.append(item[0].get('message'))
                err_msg_str = '/'.join(err_msg_list)  # 拼接错误信息为一个字符串
                return to_json_data(errno=Code.PARAMERR, errmsg=err_msg_str)
        else:
            return to_json_data(errno=Code.PARAMERR, errmsg="该文档不存在！")

# 文档管理之上传文件
class DocUploadFile(View):
    """
    URL:/admin/docs/files/
    """
    # 权限设置
    permission_required = ('doc.add_doc', 'doc.change_doc')
    raise_exception = True
    def handle_no_permission(self):
        return to_json_data(errno=Code.ROLEERR, errmsg='没有操作权限')

    # 上传
    def post(self,request):
        # 1.获取文件对象
        text_file = request.FILES.get('text_file')
        # 是否拿到
        if not text_file:
            return to_json_data(errno=Code.PARAMERR, errmsg='从前端获取文件失败')
        # 校验文件类型
        if text_file.content_type not in ('application/octet-stream', 'application/pdf',
                                          'application/zip', 'text/plain', 'application/x-rar'):
            return to_json_data(errno=Code.DATAERR, errmsg='文件格式不支持上传')
        # 获取文件后缀名
        try:
            text_ext_name = text_file.name.split('.')[-1]
        except Exception as e:
            logger.info('文件拓展名异常：{}'.format(e))
            text_ext_name = 'doc'
        # 2.上传文件对象
        try:
            upload_res = FDFS_Client.upload_by_buffer(text_file.read(), file_ext_name=text_ext_name)
        except Exception as e:
            logger.error('文件上传出现异常：{}'.format(e))
            return to_json_data(errno=Code.UNKOWNERR, errmsg='文件上传异常')
        # except没有捕获异常时执行else
        else:
            if upload_res.get('Status') != 'Upload successed.':
                logger.info('文件上传到FastDFS服务器失败')
                return to_json_data(Code.UNKOWNERR, errmsg='文件上传到服务器失败')
            else:
                text_name = upload_res.get('Remote file_id')
                text_url = settings.FASTDFS_SERVER_DOMAIN + text_name
                return to_json_data(data={'text_file': text_url}, errmsg='文件上传成功')

# 文档发布
class DocsPubView(PermissionRequiredMixin,View):
    """
    URL：/admin/docs/pub/
    """
    # 权限设置
    permission_required = ('doc.view_doc', 'doc.add_doc')
    raise_exception = True

    def handle_no_permission(self):
        if self.request.method.lower() != 'get':
            return to_json_data(errno=Code.ROLEERR, errmsg='没有操作权限')
        else:
            return super(DocsPubView, self).handle_no_permission()


            # 页面渲染
    def get(self,request):
        return render(request,'admin/doc/docs_pub.html')

    # 发布接口
    def post(self,request):
        # 1.获取参数
        json_data = request.body
        if not json_data:
            return to_json_data(errno=Code.PARAMERR, errmsg=error_map[Code.PARAMERR])
        dict_data = json.loads(json_data.decode('utf8'))  # 把获取到的json对象转化成字典
        # 2.form表单验证
        form = forms.DocsPubForm(data=dict_data)
        if form.is_valid():
            # 3.保存到数据库
            doc_instance = form.save(commit=False)  # 先缓存(因为form表单只有五个参数)
            doc_instance.author = request.user      # 给文档添加作者信息
            doc_instance.save()
            return to_json_data(errmsg="文章发布成功！")
        else:
            # 定义一个错误信息列表
            err_msg_list = []
            for item in form.errors.get_json_data().values():
                err_msg_list.append(item[0].get('message'))
            err_msg_str = '/'.join(err_msg_list)  # 拼接错误信息为一个字符串
            return to_json_data(errno=Code.PARAMERR, errmsg=err_msg_str)



# 课程管理
class CoursesManageView(PermissionRequiredMixin,View):
    """
    URL：/admin/courses/
    """
    # 权限管理
    permission_required = ('course.view_course')
    raise_exception = True

    # 页面渲染
    def get(self,request):
        courses = Course.objects.select_related('category','teacher').\
            only('title','category__name','teacher__name').filter(is_delete=False)
        return render(request,'admin/course/courses_manage.html',locals())

# 课程管理之标签操作
class CourseEditView(PermissionRequiredMixin,View):
    """
    URL：/admin/courses/<int:course_id>
    """
    # 权限设置
    permission_required = ('course.view_course', 'course.delete_course', 'course.change_course')
    raise_exception = True
    def handle_no_permission(self):
        if self.request.method.lower() != 'get':
            return to_json_data(errno=Code.ROLEERR, errmsg='没有操作权限')
        else:
            return super(CourseEditView, self).handle_no_permission()

    # 删除
    def delete(self,request,course_id):
        course = Course.objects.filter(is_delete=False, id=course_id).first()
        if course:
            course.is_delete = True
            course.save(update_fields=['is_delete', 'update_time'])
            return to_json_data(errmsg="课程删除成功")
        else:
            return to_json_data(errno=Code.PARAMERR, errmsg="需要删除的课程不存在")

    # 编辑
    def get(self,request,course_id):
        course = Course.objects.filter(is_delete=False, id=course_id).first()
        if course:
            teachers = Teacher.objects.only('name').filter(is_delete=False)
            categories = CourseCategory.objects.only('name').filter(is_delete=False)
            return render(request, 'admin/course/courses_pub.html', locals())

    # 更新接口
    def put(self,request,course_id):
        course = Course.objects.filter(is_delete=False, id=course_id).first()
        if course:
            # 1.获取前端参数
            json_data = request.body
            if not json_data:
                return to_json_data(errno=Code.PARAMERR, errmsg=error_map[Code.PARAMERR])
            dict_data = json.loads(json_data.decode('utf8'))  # 把获取到的json对象转化成字典
            # 2.form表单验证
            form = forms.CoursesPubForm(data=dict_data)
            if form.is_valid():
                # 3.保存到数据库
                for key, value in form.cleaned_data.items():
                    setattr(course, key, value)
                course.save()
                return to_json_data(errmsg="课程更新成功！")
            else:
                # 定义一个错误信息列表
                err_msg_list = []
                for item in form.errors.get_json_data().values():
                    err_msg_list.append(item[0].get('message'))
                err_msg_str = '/'.join(err_msg_list)  # 拼接错误信息为一个字符串
                return to_json_data(errno=Code.PARAMERR, errmsg=err_msg_str)
        else:
            return to_json_data(errno=Code.PARAMERR, errmsg="该课程不存在！")

# 课程发布
class CoursePubView(PermissionRequiredMixin,View):
    """
    URL:/admin/courses/pub/
    """
    # 权限设置
    permission_required = ('course.view_course', 'course.add_course')
    raise_exception = True
    def handle_no_permission(self):
        if self.request.method.lower() != 'get':
            return to_json_data(errno=Code.ROLEERR, errmsg='没有操作权限')
        else:
            return super(CoursePubView, self).handle_no_permission()

    # 页面渲染
    def get(self,request):
        teachers = Teacher.objects.only('name').filter(is_delete=False)
        categories = CourseCategory.objects.only('name').filter(is_delete=False)
        return render(request, 'admin/course/courses_pub.html', locals())

    # 发布接口
    def post(self,request):
        # 1.获取前端参数
        json_data = request.body
        if not json_data:
            return to_json_data(errno=Code.PARAMERR, errmsg=error_map[Code.PARAMERR])
        dict_data = json.loads(json_data.decode('utf8'))  # 把获取到的json对象转化成字典
        # 2.form表单验证
        form = forms.CoursesPubForm(data=dict_data)
        if form.is_valid():
            # 3.保存到数据库
            courses_instance = form.save()
            return to_json_data(errmsg='课程发布成功')
        else:
            # 定义一个错误信息列表
            err_msg_list = []
            for item in form.errors.get_json_data().values():
                err_msg_list.append(item[0].get('message'))
            err_msg_str = '/'.join(err_msg_list)  # 拼接错误信息为一个字符串
            return to_json_data(errno=Code.PARAMERR, errmsg=err_msg_str)



# 轮播图
class BannerManageView(PermissionRequiredMixin,View):
    """
    URL:/admin/banners/
    """
    # 权限修改
    permission_required = ('news.view_banner')
    raise_exception = True

    # 页面渲染
    def get(self,request):
        banners = models.Banner.objects.only('image_url','priority').\
                filter(is_delete=False).order_by('priority')[0:constants.SHOW_BANNER_COUNT]
        priority_dict = dict(models.Banner.PTL_CHOICES)  # 元祖转字典
        return render(request,'admin/news/news_banner.html',locals())

# 轮播图更新，删除
class BannerEditView(PermissionRequiredMixin,View):
    """
    URL:/admin/banners/<int:banner_id>/
    """
    # 权限修改
    permission_required = ('news.delete_banner', 'news.change_banner')
    raise_exception = True
    def handle_no_permission(self):
        return to_json_data(errno=Code.ROLEERR, errmsg='没有操作权限')

    # 删除
    def delete(self,request,banner_id):
        banner = models.Banner.objects.only('id').filter(id=banner_id).first()
        if banner:
            banner.is_delete = True
            banner.save(update_fields=['is_delete'])
            return to_json_data(errmsg='文章删除成功!')
        else:
            return to_json_data(errno=Code.PARAMERR, errmsg="该文章不存在！")

    # 更新
    def put(self, request, banner_id):
        """
        1.图片不变，验证优先级是否变化
        2.图片改变，不用验证优先级，直接保存
        """
        # 1.获取参数
        json_data = request.body
        if not json_data:
            return to_json_data(errno=Code.PARAMERR, errmsg=error_map[Code.PARAMERR])
        # 把获取到的json对象转化成字典
        dict_data = json.loads(json_data.decode('utf8'))

        # 2.优先级验证
        try:
            priority = int(dict_data.get('priority'))  # 字符串转换
            priority_list = [i for i, _ in models.HotNews.PTL_CHOICES]  # 使用了列表生成式只拿i,不需要的用_代替
            if priority not in priority_list:
                return to_json_data(errno=Code.PARAMERR, errmsg='轮播图优先级设置错误!')
        except Exception as e:
            logger.info('轮播图优先级异常:\n{}'.format(e))
            return to_json_data(errno=Code.PARAMERR, errmsg='轮播图优先级设置错误!')

        # 3.图片验证
        image_url = dict_data.get('image_url')
        old_banner = models.Banner.objects.only('image_url','priority').filter(id=banner_id).first()
        if not image_url:
            return to_json_data(errno=Code.PARAMERR, errmsg='轮播图url为空')
        if old_banner.priority == priority and old_banner.image_url == image_url:
            return to_json_data(errno=Code.PARAMERR, errmsg='轮播图参数未修改')

        old_banner.image_url = image_url
        old_banner.priority = priority
        old_banner.save(update_fields=['priority','image_url','update_time'])
        return to_json_data(errmsg="轮播图修改成功！")


# 添加轮播图
class BannerAddView(PermissionRequiredMixin,View):
    """
    URL:/admin/banners/add/
    """
    # 权限设置
    permission_required = ('news.view_banner', 'news.add_banner')
    raise_exception = True
    def handle_no_permission(self):
        if self.request.method.lower() != 'get':
            return to_json_data(errno=Code.ROLEERR, errmsg='没有操作权限')
        else:
            return super(BannerAddView, self).handle_no_permission()

    # 添加页面渲染
    def get(self, request):
        # 查询tag表中id,name两字段，以news表中每个tag_id对应的news数量分组(value查询返回字典)
        tags = models.Tag.objects.values('id', 'name').annotate(num_news=Count('news')). \
            filter(is_delete=False).order_by('num_news')
        priority_dict = dict(models.Banner.PTL_CHOICES)  # 元祖转字典
        return render(request, 'admin/news/news_banner_add.html', locals())

    # 添加后保存
    def post(self, request):
        """" 只需要三个参数：news_id,优先级，image_url """
        # 1.获取前端参数
        json_data = request.body
        if not json_data:
            return to_json_data(errno=Code.PARAMERR, errmsg=error_map[Code.PARAMERR])
        dict_data = json.loads(json_data.decode('utf8'))     # 把获取到的json对象转化成字典

        # 2.news_id的验证
        try:
            news_id = int(dict_data.get('news_id'))
        except Exception as e:
            logger.info('对应文章:\n{}'.format(e))
            return to_json_data(errno=Code.PARAMERR, errmsg='参数错误')
        if not models.News.objects.filter(id=news_id,is_delete=False).exists():
            return to_json_data(errno=Code.PARAMERR, errmsg='文章不存在')

        # 3.优先级的验证
        try:
            priority = int(dict_data.get('priority'))
            priority_list = [i for i, _ in models.Banner.PTL_CHOICES]
            if priority not in priority_list:
                return to_json_data(errno=Code.PARAMERR, errmsg='优先级设置错误')
        except Exception as e:
            logger.info('轮播图优先级异常：\n{}'.format(e))
            return to_json_data(errno=Code.PARAMERR, errmsg='优先级设置错误')

        # 4.image_url验证
        image_url = dict_data.get('image_url')
        if not image_url:
            return to_json_data(errno=Code.PARAMERR, errmsg='轮播图url为空')
        if models.Banner.objects.filter(image_url=image_url).exists():
            return to_json_data(errno=Code.PARAMERR, errmsg='图片已存在')

        # 5.存数据库中
        banner_tuple = models.Banner.objects.get_or_create(news_id=news_id)
        banner, is_created = banner_tuple
        banner.priority = priority  # 修改优先级
        banner.image_url = image_url  # 修改优先级
        banner.save(update_fields=['priority','image_url','update_time'])
        return to_json_data(errmsg="轮播图创建成功")



# 组管理
class GroupManageView(PermissionRequiredMixin,View):
    """
    URL:/admin/groups/
    """
    # 权限设置
    permission_required = ('news.view_course')
    raise_exception = True

    # 页面渲染
    def get(self,request):
        # 分组查询：用user表中的数量进行分组
        groups = Group.objects.values('id', 'name').annotate(num_users=Count('user')).\
            order_by('-num_users', 'id')
        return render(request, 'admin/user/groups_manage.html', locals())

# 组管理之标签操作
class GroupEditView(PermissionRequiredMixin,View):
    """
    URL:/admin/groups/<int:group_id>
    """
    # 权限设置
    permission_required = ('auth.view_group', 'auth.delete_group', 'auth.change_group')
    raise_exception = True
    def handle_no_permission(self):
        if self.request.method.lower() != 'get':
            return to_json_data(errno=Code.ROLEERR, errmsg='没有操作权限')
        else:
            return super(GroupEditView, self).handle_no_permission()

    # 删除
    def delete(self, request, group_id):
        group = Group.objects.only('id').filter(id=group_id).first()
        if group:
            # group.permissions.clear()     # group表没有is_delete字段,需要先将关联表里权限清空
            # group.user_set.clear()        # 反向清空和user表关联数据
            group.delete()                # 物理删除 （多对多关系物理删除时会自动级联删除，可以不写上面两条）
            return to_json_data(errmsg='用户组删除成功!')
        else:
            return to_json_data(errno=Code.PARAMERR, errmsg="该用户组不存在！")

    # 编辑
    def get(self,request,group_id):
        group = Group.objects.filter(id=group_id).first()
        if group:
            permissions = Permission.objects.only('id').all()
            return render(request,'admin/user/groups_add.html',locals())
        else:
            return Http404("用户组不存在！")

    # 更新接口
    def put(self,request,group_id):
        group = Group.objects.filter(id=group_id).first()
        if group:
            # 1.获取前端参数
            json_data = request.body
            if not json_data:
                return to_json_data(errno=Code.PARAMERR, errmsg=error_map[Code.PARAMERR])
            dict_data = json.loads(json_data.decode('utf8'))   # 将json转化为dict

            # 取出需要验证的字段
            group_name = dict_data.get('name','').strip()      # strip:去两边空格
            group_permissions = dict_data.get('group_permissions')

            # 2.验证组的名称
            if not group_name:
                return to_json_data(errno=Code.PARAMERR, errmsg='组名为空！')
            if group_name != group.name and Group.objects.filter(name=group_name).exists():
                return to_json_data(errno=Code.PARAMERR, errmsg='组名已存在')

            # 3.验证权限
            if not group_permissions:
                return to_json_data(errno=Code.PARAMERR, errmsg='权限参数为空')
            try:
                permissions_set = set(int(i) for i in group_permissions)   # 对前端拿到的进行int转换，set去重
            except Exception as e:
                logger.info('传的权限参数异常：\n{}'.format(e))
                return to_json_data(errno=Code.PARAMERR, errmsg='权限参数异常')

            all_permisssions_set = set(i.id for i in Permission.objects.only('id'))  # 数据库中获取所有的Permission的id
            if not permissions_set.issubset(all_permisssions_set):  # 判断前端获取的id是不是数据库查到的id的子集
                return to_json_data(errno=Code.PARAMERR, errmsg='有不存在的权限参数')

            # 4.设置权限，存入数据库
            for per_id in permissions_set:    # 取出每一个权限id
                p = Permission.objects.get(id=per_id)   # 拿到每条权限的实例对象
                group.permissions.add(p)       # 添加到组的权限中（add添加单个）
            group.name = group_name
            group.save()
            return to_json_data(errmsg='用户组更新成功')

        else:
            return to_json_data(errno=Code.NODATA, errmsg='需要更新的用户组不存在')

# 组创建
class GroupAddView(PermissionRequiredMixin,View):
    """
    URL:/admin/groups/add/
    """
    # 权限设置
    permission_required = ('auth.view_group', 'auth.add_group')
    raise_exception = True
    def handle_no_permission(self):
        if self.request.method.lower() != 'get':
            return to_json_data(errno=Code.ROLEERR, errmsg='没有操作权限')
        else:
            return super(GroupAddView, self).handle_no_permission()


    # 页面渲染
    def get(self,request):
        permissions = Permission.objects.only('id')
        return render(request,'admin/user/groups_add.html',locals())

    # 创建接口
    def post(self,request):
        # 1.获取前端参数
        json_data = request.body
        if not json_data:
            return to_json_data(errno=Code.PARAMERR, errmsg=error_map[Code.PARAMERR])
        dict_data = json.loads(json_data.decode('utf8'))  # 将json转化为dict

        # 取出需要验证的字段
        group_name = dict_data.get('name', '').strip()  # strip:去两边空格
        group_permissions = dict_data.get('group_permissions')

        # 2.验证组的名称
        if not group_name:
            return to_json_data(errno=Code.PARAMERR, errmsg='组名为空！')

        new_group, is_created = Group.objects.get_or_create(name=group_name)
        if not is_created:
            return to_json_data(errno=Code.PARAMERR, errmsg='组名已存在')

        # 3.验证权限
        if not group_permissions:
            return to_json_data(errno=Code.PARAMERR, errmsg='权限参数为空')
        try:
            permissions_set = set(int(i) for i in group_permissions)  # 对前端拿到的进行int转换，set去重
        except Exception as e:
            logger.info('传的权限参数异常：\n{}'.format(e))
            return to_json_data(errno=Code.PARAMERR, errmsg='权限参数异常')

        all_permisssions_set = set(i.id for i in Permission.objects.only('id'))  # 数据库中获取所有的Permission的id
        if not permissions_set.issubset(all_permisssions_set):  # 判断前端获取的id是不是数据库查到的id的子集
            return to_json_data(errno=Code.PARAMERR, errmsg='有不存在的权限参数')

        # 4.设置权限,存入数据库
        for per_id in permissions_set:  # 取出每一个权限id
            p = Permission.objects.get(id=per_id)  # 拿到每条权限的实例对象
            new_group.permissions.add(p)  # 添加到组的权限中
        new_group.save()
        return to_json_data(errmsg='用户组创建成功')




# 用户管理
class UsersManageView(PermissionRequiredMixin,View):
    """
    URL:/admin/users/
    """
    # 权限设置
    permission_required = ('users.view_users')
    raise_exception = True

    def get(self,reqeuest):
        users = Users.objects.only('username','is_staff','is_superuser').\
            filter(is_active=True)        # is_active:user表中的逻辑删除
        return render(reqeuest,'admin/user/users_manage.html',locals())

    # 多对多的数据操作：add remove clear  正向查：.属性   反向查： .类名小写_set

# 用户管理之标签操作
class UsersEditView(PermissionRequiredMixin,View):
    """
    URL:/admin/users/<int:user_id>
    """
    # 权限设置
    permission_required = ('user.view_users', 'user.change_users', 'user.delete_users')
    raise_exception = True
    def handle_no_permission(self):
        if self.request.method.lower() != 'get':
            return to_json_data(errno=Code.ROLEERR, errmsg='没有操作权限')
        else:
            return super(UsersEditView, self).handle_no_permission()

    # 删除
    def delete(self, request, user_id):
        user_instance = Users.objects.filter(id=user_id).first()
        if user_instance:
            user_instance.groups.clear()  # 清除用户组
            user_instance.user_permissions.clear()  # 清除用户权限
            user_instance.is_active = False  # 设置为不激活状态
            user_instance.save()
            return to_json_data(errmsg="用户删除成功")
        else:
            return to_json_data(errno=Code.PARAMERR, errmsg="需要删除的用户不存在")

    # 编辑
    def get(self,request,user_id):
        user_instance = Users.objects.filter(id=user_id).first()
        if user_instance:
            groups = Group.objects.only('name').all()
            return render(request, 'admin/user/users_edit.html',locals())
        else:
            return Http404('该用户不存在！')

    # 更新接口
    def put(self,request,user_id):
        user_instance = Users.objects.filter(id=user_id).first()
        if user_instance:
            # 1.获取前端参数
            json_data = request.body
            if not json_data:
                return to_json_data(errno=Code.PARAMERR, errmsg=error_map[Code.PARAMERR])
            dict_data = json.loads(json_data.decode('utf8'))  # 将json转化为dict
            # 2.验证 is_staff，is_active，is_superuser
            try:
                groups = dict_data.get('groups')              # 拿到的是group_id
                is_staff = int(dict_data.get('is_staff'))
                is_active= int(dict_data.get('is_active'))
                is_superuser = int(dict_data.get('is_superuser'))
                params = (is_staff,is_active,is_superuser)          # 放到一个元组里
                # in方法满足返回True，不满足返回False;all方法判断返回的是不是都是True
                if not all([p in (0, 1) for p in params]):
                    return to_json_data(errno=Code.PARAMERR, errmsg='参数错误')
            except Exception as e:
                logger.error('从前端获取参数出现异常：{}'.format(e))
                return to_json_data(errno=Code.PARAMERR, errmsg='参数错误')

            # 3.用户组验证
            try:
                groups_set = set(int(i) for i in groups)  # 前端获取的groups循环出来的是字符串，要进行int转换，set去重
            except Exception as e:
                logger.error('传入的用户组参数异常：{}'.format(e))
                return to_json_data(errno=Code.PARAMERR, errmsg='用户组参数异常')
            # 从Group表获取所有的group.id
            all_group_set = set(i.id for i in Group.objects.only('id'))
            # 判断groups_set是否是all_group_set的子集
            if not groups_set.issubset(all_group_set):
                return to_json_data(errno=Code.PARAMERR, errmsg='有不存在的用户组')

            # 4.存入数据库
            gs = Group.objects.filter(id__in=groups_set)    # 拿到用户组的实例对象
            user_instance.groups.clear()         # 清空原来的用户组信息
            user_instance.groups.set(gs)         # 添加用户组信息(set是添加多个)

            user_instance.is_staff = bool(is_staff)
            user_instance.is_active = bool(is_active)
            user_instance.is_superuser = bool(is_superuser)
            user_instance.save()
            return to_json_data(errmsg='用户信息更新成功！')

        else:
            return to_json_data(errno=Code.PARAMERR, errmsg="需要更新的用户不存在！")





