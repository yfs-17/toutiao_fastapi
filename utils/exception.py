import traceback
from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette import status
# 开发模式：返回详细错误信息
# ⽣产模式：返回简化错误信息
DEBUG_MODE = True # 教学项⽬保持开启
async def http_exception_handler(request: Request, exc: HTTPException):
     """
     处理 HTTPException 异常
     """
     # HTTPException 通常是业务逻辑主动抛出的，data 保持 None
     return JSONResponse(
         status_code=exc.status_code,
         content={
             "code": exc.status_code,
             "message": exc.detail,
             "data": None
         }
     )
async def integrity_error_handler(request: Request, exc: IntegrityError):
         """
         处理数据库完整性约束错误
         """
         error_msg = str(exc.orig)
         # 判断具体的约束错误类型
         if "username_UNIQUE" in error_msg or "Duplicate entry" in error_msg:
             detail = "⽤户名已存在"
         elif "FOREIGN KEY" in error_msg:
             detail = "关联数据不存在"
         else:
             detail = "数据约束冲突，请检查输⼊"
         # 开发模式下返回详细错误信息
         error_data = None
         if DEBUG_MODE:
             error_data = {"error_type": "IntegrityError",
                 "error_detail": error_msg,
                 "path": str(request.url)
             }
         return JSONResponse(
             status_code=status.HTTP_400_BAD_REQUEST,
             content={
             "code": 400,
             "message": detail,
             "data": error_data
             }
         )
async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError):
         """
         处理 SQLAlchemy 数据库错误
         """
         # 开发模式下返回详细错误信息
         error_data = None
         if DEBUG_MODE:
             error_data = {
             "error_type": type(exc).__name__,
             "error_detail": str(exc),
             "traceback": traceback.format_exc(),
             "path": str(request.url)
             }
         return JSONResponse(
             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
             content={
                 "code": 500,
                 "message": "数据库操作失败，请稍后重试",
                 "data": error_data
             }
         )
async def general_exception_handler(request: Request, exc: Exception):
         """
         处理所有未捕获的异常
         """
         # 开发模式下返回详细错误信息
         error_data = None
         if DEBUG_MODE:
             error_data = {"error_type": type(exc).__name__,
                 "error_detail": str(exc),
                 # 格式化异常信息为字符串，⽅便⽇志记录和调试
                 "traceback": traceback.format_exc(),
                 "path": str(request.url)
             }
         return JSONResponse(
             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
             content={
                 "code": 500,
                 "message": "服务器内部错误",
                 "data": error_data
             }
         )


# 参数字段名 -> 中文提示
FIELD_LABELS = {
    "username": "用户名",
    "password": "密码",
    "oldPassword": "原密码",
    "newPassword": "新密码",
    "categoryId": "分类 ID",
    "conversationId": "会话 ID",
    "newsId": "新闻 ID",
    "pageSize": "每页数量",
}


async def validation_exception_handler(request: Request, exc: RequestValidationError):
         """
         处理请求参数校验失败（Pydantic 422）

         默认返回是英文的嵌套结构，这里转成一句能直接展示给用户的中文提示。
         """
         errors = exc.errors()
         first = errors[0] if errors else {}
         # loc 形如 ('body', 'password')，去掉 body/query 这类位置标记
         parts = [str(p) for p in first.get("loc", []) if p not in ("body", "query", "path")]
         field = parts[-1] if parts else "参数"
         label = FIELD_LABELS.get(field, field)
         ctx = first.get("ctx", {}) or {}
         error_type = first.get("type", "")

         if error_type == "string_too_short":
             detail = f"{label}长度不能少于 {ctx.get('min_length')} 个字符"
         elif error_type == "string_too_long":
             detail = f"{label}长度不能超过 {ctx.get('max_length')} 个字符"
         elif error_type == "missing":
             detail = f"缺少必填项：{label}"
         elif error_type in ("int_parsing", "bool_parsing", "float_parsing"):
             detail = f"{label}格式不正确"
         else:
             detail = f"{label}填写有误，请检查后重试"

         error_data = {"errors": errors} if DEBUG_MODE else None
         return JSONResponse(
             status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
             content={
                 "code": 422,
                 "message": detail,
                 "data": error_data
             }
         )