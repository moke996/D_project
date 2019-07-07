from django.db import models

class ModelBase(models.Model):
    """
    每一个表中都有的字段放到一个基类模型中
    """
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")   # True:自动添加时间
    update_time = models.DateTimeField(auto_now=True, verbose_name="更新时间")       # True:更新时自动更新时间
    is_delete = models.BooleanField(default=False,verbose_name="逻辑删除")           # 布尔类型,只有true和false两种结果


    class Meta:
        """
         为抽象模型类, 用于其他模型来继承，数据库迁移时不会创建ModelBase表
        """
        abstract = True
