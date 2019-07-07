import json
from django.shortcuts import render,redirect,reverse
from django.views import View
from django.contrib.auth import login,logout
from utils.json_fun import to_json_data
from utils.user_reg_code import Code, error_map
from user.forms import RegisterForm, LoginForm
from user.models import Users

# 注册
class RegisterView(View):
    """
     /register/
    """
    def get(self,request):
        return render(request, 'users/register.html')
    """
    点击立即注册，需要验证的：用户名，密码，确认密码，手机号，短信验证码
    请求方式：POST
    提交方式：ajax或者form表单
    后端：获取参数，校验参数，存入数据库，返回给前端
    """
    def post(self,request):
        # 1.获取参数(ajax数据存在body中)
        json_data = request.body
        # 没获取到就返回错误码
        if not json_data:
            return to_json_data(errno=Code.PARAMERR, errmsg=error_map[Code.PARAMERR])
        dict_data = json.loads(json_data.decode('utf8'))  # 把获取到的json对象转化成字典
        # 2.校验参数
        form = RegisterForm(data=dict_data)
        if form.is_valid():
            # 3.存入数据库
            username = form.cleaned_data.get('username')    # 从form表单中获取数据
            password = form.cleaned_data.get('password')
            mobile = form.cleaned_data.get('mobile')
            user = Users.objects.create_user(username=username,password=password,mobile=mobile)
            login(request,user)
            # 4.返回给前端
            return to_json_data(errmsg="注册成功")
        else:
            # 定义一个错误信息列表
            err_msg_list = []
            for item in form.errors.get_json_data().values():
                err_msg_list.append(item[0].get('message'))
            err_msg_str = '/'.join(err_msg_list)  # 拼接错误信息为一个字符串

            return to_json_data(errno=Code.PARAMERR, errmsg=err_msg_str)


# 登录
class LoginView(View):

    def get(self,request):
        return render(request,'users/login.html')

    def post(self,request):
        """
           参数：登录账号，密码，记住密码
           请求方式：POST
           提交：ajax
        """
        # 1.获取前端参数
        json_data = request.body
        if not json_data:
            return to_json_data(errno=Code.PARAMERR, errmsg=error_map[Code.PARAMERR])
        # 把获取到的json对象转化成字典
        dict_data = json.loads(json_data.decode('utf8'))
        # 2.在form表单中校验数据
        form = LoginForm(data=dict_data, request=request)    # 类的实例化
        # 3.返回给前端
        if form.is_valid():
            return to_json_data(errmsg='登陆成功！')
        else:
            # 定义一个错误信息列表返回
            err_msg_list = []
            for item in form.errors.get_json_data().values():
                err_msg_list.append(item[0].get('message'))
            err_msg_str = '/'.join(err_msg_list)  # 拼接错误信息为一个字符串
            return to_json_data(errno=Code.PARAMERR, errmsg=err_msg_str)

# 退出登录
class LogoutView(View):
    def get(self, request):
        logout(request)       # django中auth提供的一个方法
        return redirect(reverse('news:index'))






