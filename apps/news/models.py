from django.db import models
from utils.models import ModelBase  # 用来继承的三个字段
from django.core.validators import MinLengthValidator

# 文章分类表
class Tag(ModelBase):
    """
    name：标签名称
    """
    name = models.CharField(max_length=64, verbose_name="标签名", help_text="标签名")

    class Meta:
        ordering = ['-update_time','-id']        # 排序：按照更新时间，id从大到小排序
        db_table = "tb_tag"                 # 数据库中创建的表名
        verbose_name = "新闻标签"            # 在admin站点中显示的名称
        verbose_name_plural = verbose_name  # 显示的复数名称

    def __str__(self):
        return self.name                    # 访问Tag实例，返回标签名称给我们


# 文章表
class News(ModelBase):
    """
     title  digest(摘要)  content clicks(访问量)   image_url
     author(作者，关联用户表一对多(一个人写多文章))
     tag(外键关联一对多(一个分类多篇文章))
    """
    # models.CharField中没有提供min_length参数，需要使用校验器才能设置最小长度
    title = models.CharField(max_length=150, validators=[MinLengthValidator(1)],verbose_name="标题", help_text="标题")
    digest = models.CharField(max_length=200, validators=[MinLengthValidator(1)],verbose_name="摘要", help_text="摘要")
    content = models.TextField(verbose_name="内容", help_text="内容")
    clicks = models.IntegerField(default=0, verbose_name="点击量", help_text="点击量")
    image_url = models.URLField(default="", verbose_name="图片url", help_text="图片url")

    # on_delete:当Tag中删除了某分类，则New中文章类别为None
    tag = models.ForeignKey('Tag', on_delete=models.SET_NULL, null=True)
    # on_delete:当作者不存在，则New中文章作者为None
    author = models.ForeignKey('user.Users', on_delete=models.SET_NULL, null=True)

    class Meta:
        ordering = ['-update_time', '-id']      # 排序
        db_table = "tb_news"                    # 指明数据库表名
        verbose_name = "新闻"                   # 在admin站点中显示的名称
        verbose_name_plural = verbose_name      # 显示的复数名称

    def __str__(self):
        return self.title          # 访问News实例，返回新闻标题称给我们


# 评论表
class Comments(ModelBase):
    """
     content(评论内容)
     author(评论人，关联用户表一对多(一个用户写多条评论))
     news(哪篇文章，关联文章表一对多(一篇文章有多条评论))
    """
    content = models.TextField(verbose_name="内容", help_text="内容")
    author = models.ForeignKey('user.Users', on_delete=models.SET_NULL, null=True)
    # 级联删除，也就是当删除主表的数据时候从表中的数据也随着一起删除
    news = models.ForeignKey('News', on_delete=models.CASCADE)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)

    # 生成序列化输出的字典
    def to_dict_data(self):
        comment_dict = {
            'news_id': self.news_id,
            'comment_id': self.id,
            'content': self.content,
            'author': self.author.username,
            'update_time': self.update_time.strftime('%Y年%m月%d日 %H:%M'),
            'parent': self.parent.to_dict_data() if self.parent else None
        }
        return comment_dict


    class Meta:
        ordering = ['-update_time', '-id']        # 排序
        db_table = "tb_comments"                  # 指明数据库表名
        verbose_name = "评论"                     # 在admin站点中显示的名称
        verbose_name_plural = verbose_name        # 显示的复数名称

    def __str__(self):
        return '<评论{}>'.format(self.id)


# 热门文章表
class HotNews(ModelBase):
    """
    news(关联文章一对一)
    priority(优先级)
    """
    PTL_CHOICES = [
        (1, '第一级'),
        (2, '第二级'),
        (3, '第三级'),
    ]
    # models.CASCADE：级联删除
    news = models.OneToOneField('News', on_delete=models.CASCADE)
    # choices限制优先级范围
    priority = models.IntegerField(choices=PTL_CHOICES, default=3, verbose_name="优先级", help_text="优先级")

    class Meta:
        ordering = ['-update_time', '-id']          # 排序
        db_table = "tb_hotnews"                     # 指明数据库表名
        verbose_name = "热门新闻"                    # 在admin站点中显示的名称
        verbose_name_plural = verbose_name          # 显示的复数名称

    def __str__(self):
        return '<热门新闻{}>'.format(self.id)


# 轮播图表
class Banner(ModelBase):
    """
    image_url   priority(优先级)   news(关联文章一对一)
    """
    PTL_CHOICES = [
        (1, '第一级'),
        (2, '第二级'),
        (3, '第三级'),
        (4, '第四级'),
        (5, '第五级'),
        (6, '第六级'),
    ]
    image_url = models.URLField(verbose_name="轮播图url", help_text="轮播图url")
    # choices限制优先级范围
    priority = models.IntegerField(choices=PTL_CHOICES, default=6, verbose_name="优先级", help_text="优先级")
    # models.CASCADE：级联删除
    news = models.OneToOneField('News', on_delete=models.CASCADE)

    class Meta:
        ordering = ['priority', '-update_time', '-id']  # 排序
        db_table = "tb_banner"                          # 指明数据库表名
        verbose_name = "轮播图"                          # 在admin站点中显示的名称
        verbose_name_plural = verbose_name              # 显示的复数名称

    def __str__(self):
        return '<轮播图{}>'.format(self.id)

