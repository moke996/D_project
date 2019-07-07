import logging
from django.shortcuts import render
from django.views import View
from django.http import Http404
from . import models

logger = logging.getLogger('django')


# 在线课堂页面
def course_list(request):
    # 缩略图 视频标题 讲师 职称
    courses = models.Course.objects.select_related('teacher').\
        only('title','cover_url','teacher__name','teacher__profile').\
        filter(is_delete=False)
    return render(request,'course/course.html',locals())


# 视频播放页
class CourseDetailView(View):
    """
    参数：title,cover_url,video_url,duration,profile,outline,还有teacher相关字段
    URL:/course/<int:course_id>/
    """
    def get(self,request,course_id):
        try:
            course = models.Course.objects.select_related('teacher').\
                only('title','cover_url','video_url','duration','profile','outline',
                     'teacher__name','teacher__avatar_url','teacher__positional_title').\
                filter(is_delete=False,id=course_id).first()
            return render(request,'course/course_detail.html',locals())
        except models.Course.DoesNotExist as e:
                    logger.info("当前课程出现如下异常：\n{}".format(e))
                    raise Http404("此课程不存在！")


