import json
import logging
from django.shortcuts import render
from django.views import View
from django.http import Http404
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger  # django中的分页方法
from haystack.views import SearchView as _SearchView        # 搜索页

from D_project import settings
from news import models
from news import  constants
from utils.json_fun import to_json_data
from utils.user_reg_code import Code,error_map

# 日志器
logger = logging.getLogger('django')


# 首页
class IndexView(View):
    """使用context渲染"""
    def get(self, request):
        # 文章标签导航实现
        tags = models.Tag.objects.only('id', 'name').filter(is_delete=False)
        # 热门新闻功能实现
        hot_news = models.HotNews.objects.select_related('news').\
            only('news__title','news__image_url','news_id').filter(is_delete=False).\
            order_by('priority','-news__clicks')[0:constants.SHOW_HOTNEWS_COUNT]
            # order_by:从优先级或者点击量(从大到小)进行排序,[]:切片方法显示1-3条
        # context = {
        #     'tags': tags
        # }
        # return render(request, 'news/index.html',context=context)
        return render(request, 'news/index.html', locals())     # locals()方法代替context{}方法


# 新闻列表页
class NewsListView(View):
    """
     前端发送：ajax请求
     传参：tag_id(标签分类id)   page(标签下对应文章页数)
     后台返回：7个字段
     请求方式：GET（只是查询，不涉及其他）
     url定义：/news/?tag_id=1&page=2
    """
    def get(self, request):
        # 1.获取前端参数
        # 2.校验参数:正常传参(传数字)，异常传参(爬虫程序传来字母)
        try:
            tag_id = int(request.GET.get('tag_id', 0))   # 拿到的是字符串类型，需要转换;没有传参就为0
        except Exception as e:
            logger.error("传入标签错误:\n{}".format(e))   # 写入日志器
            tag_id = 0
        try:
            page = int(request.GET.get('page', 1))
        except Exception as e:
            logger.error("页码错误:\n{}".format(e))
            page = 1

        # 3.从数据库拿数据
        # select_related:优化查询,当执行它的查询时它沿着外键关系查询关联的对象数据
        news_queryset = models.News.objects.select_related('tag','author').only('title','image_url'
                        ,'digest','update_time','tag__name','author__username').filter()
        # 传了tag_id按标签查，没传就查询数据库所有的
        news= news_queryset.filter(is_delete=False, tag_id=tag_id) or news_queryset.filter(is_delete=False)

        # 4.分页
        paginator = Paginator(news, constants.PER_PAGE_NEWS_COUNT)   # 对news进行分页，每页xx条
        try:
            news_info = paginator.page(page)     # 拿到具体某一页的信息,是quertset类型
        except EmptyPage:                        # 例如：最多5页，传的page>5
            logger.error("访问页数不存在！")
            news_info = paginator.page(paginator.num_pages)     # 返回最后一页(num_pages代表总页数)

        # 5.序列化输出
        news_info_list = []
        for n in news_info:
            news_info_list.append({
                'id': n.id,
                'title': n.title,
                'digest': n.digest,
                'image_url': n.image_url,
                'update_time': n.update_time.strftime('%Y年%m月%d日 %H:%M'),    # 格式化时间
                'tag_name': n.tag.name,
                'author': n.author.username,
            })
        data = {
            'news': news_info_list,
            'total_pages': paginator.num_pages
        }
        # 6.返回数据给前端
        return to_json_data(data=data)


# 轮播图
class NewsBannerView(View):
    """
    请求方法：GET
    url定义：/news/banners/
    请求参数：前端无需传入参数
    ajax渲染，后端返回json格式数据
    """
    def get(self,request):
        # 1.数据库中查询返回字段
        banners = models.Banner.objects.select_related('news').only('image_url','news_id','news__title').\
            filter(is_delete=False).order_by('priority')[0:constants.SHOW_BANNER_COUNT]
        # 2.序列化输出
        banners_info_list = []
        for b in banners:
            banners_info_list.append(
                {
                    'image_url': b.image_url,
                    'news_id': b.news_id,
                    'new_title': b.news.title,
                }
            )
        data = {
            'banners': banners_info_list
        }
        return to_json_data(data=data)


# 文章详情页
class NewDetailView(View):
    """
    前端传参：news_id
    后台返回：title,author,update_time,tag_name, content
    url定义:'/news/<int:news_id>'
    """
    def get(self,request,news_id):
        # 文章详情
        news = models.News.objects.select_related('tag', 'author').\
            only('title','author', 'update_time','tag__name','content').\
            filter(is_delete=False, id=news_id).first()
        if news:
            # 评论部分字段：author,content,update_time, parent.username, parent.content, parent.update_time
            comments = models.Comments.objects.select_related('author', 'parent').\
                only('content', 'update_time', 'author__username', 'parent__content',
                     'parent__author__username', 'parent__update_time').\
                filter(is_delete=False,news_id=news_id)
            # 序列化输出(字典在模型中生成)
            comments_list = []
            for c in comments:
                comments_list.append(c.to_dict_data())   # c.to_dict_data()调用模型类的方法
            return render(request,'news/news_detail.html',locals())
        else:
            raise Http404('文章{}不存在'.format(news_id))


# 文章评论
class NewsCommentView(View):
    """
    前端传参：news_id(通过url传递),content,parent_id(也可以没有)，当前用户：request.user
    URL:/news/<int:news_id>/comments/
    """
    def post(self,request,news_id):
        # 1.获取参数
        if not request.user.is_authenticated:         # 判断是否登录
            return to_json_data(errno=Code.SESSIONERR,errmsg=error_map[Code.SESSIONERR])

        if not models.News.objects.only('id').filter(is_delete=False,id=news_id):
            return to_json_data(errno=Code.PARAMERR,errmsg='新闻不存在')

        json_data = request.body       # 从body中获取
        if not json_data:
            return to_json_data(errno=Code.PARAMERR, errmsg=error_map[Code.PARAMERR])
        dict_data = json.loads(json_data.decode('utf8'))

        # 2.校验参数
        content = dict_data.get('content')
        if not content:
            return to_json_data(errno=Code.PARAMERR, errmsg='评论内容不能为空')

        # 父评论验证：是否存在，parent_id必须为数字，数据库是否存在, 父评论新闻id是否等于news_id
        parent_id = dict_data.get('parent_id')
        try:
            if parent_id:
                parent_id = int(parent_id)
                if not models.Comments.objects.only('id').filter(is_delete=False,id=parent_id,
                                                                news_id=news_id).exists():
                    return to_json_data(errno=Code.PARAMERR, errmsg=error_map[Code.PARAMERR])
        except Exception as e:
            logger.info('前端传的parent_id有误{}'.format(e))
            return to_json_data(errno=Code.PARAMERR, errmsg='未知错误')

        # 3.存入数据库
        new_comment = models.Comments()
        new_comment.content = content
        new_comment.news_id = news_id
        new_comment.author = request.user
        new_comment.parent_id = parent_id if parent_id else None
        new_comment.save()

        # 4.返回给前端
        return to_json_data(data=new_comment.to_dict_data())   # 调用模型中的序列化输出


# 搜索页
class SearchView(_SearchView):             # 使用haystack一个查询的类
    # 模版文件
    template = 'news/search.html'
    # 重写响应方式，如果请求参数q为空，返回模型News的热门新闻数据，否则根据参数q搜索相关数据
    def create_response(self):
        kw = self.request.GET.get('q', '')
        if not kw:
            show_all = True     # 显示所有数据
            hot_news = models.HotNews.objects.select_related('news'). \
                only('news__title', 'news__image_url', 'news__id'). \
                filter(is_delete=False).order_by('priority', '-news__clicks')
            # 对搜索结果进行分页
            paginator = Paginator(hot_news, settings.HAYSTACK_SEARCH_RESULTS_PER_PAGE)
            try:
                # 拿到page具体参数，没有就默认获取第1页
                page = paginator.page(int(self.request.GET.get('page', 1)))
            except PageNotAnInteger:
                # 如果参数page的数据类型不是整型，则返回第一页数据
                page = paginator.page(1)
            except EmptyPage:
                # 用户访问的页数大于实际页数，则返回最后一页的数据
                page = paginator.page(paginator.num_pages)
            return render(self.request, self.template, locals())
        else:
            show_all = False
            qs = super(SearchView, self).create_response()
            return qs
