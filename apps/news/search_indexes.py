# -*- coding:utf-8 -*-

from haystack import indexes
# from haystack import site
from .models import News

# 指定对于某个类的某些数据建立索引
# 索引类名格式:模型类名+Index
class NewsIndex(indexes.SearchIndex, indexes.Indexable):
    """
    News索引数据模型类
    """
    # 索引字段 use_template=True指定根据表中的哪些字段建立索引文件的说明放在一个文件中
    text = indexes.CharField(document=True, use_template=True)

    # 写model_attr,使用时可以直接news.id；不写就得news.object.id
    id = indexes.IntegerField(model_attr='id')
    title = indexes.CharField(model_attr='title')
    digest = indexes.CharField(model_attr='digest')
    content = indexes.CharField(model_attr='content')
    image_url = indexes.CharField(model_attr='image_url')

    def get_model(self):
        """
        返回建立索引的模型类
        """
        return News

    def index_queryset(self, using=None):
        """返
        回要建立索引的数据查询集
        """
        # return self.get_model().objects.filter(is_delete=False, tag_id=1)
        return self.get_model().objects.filter(is_delete=False, tag_id__in=[1, 2, 3, 4, 5, 6])