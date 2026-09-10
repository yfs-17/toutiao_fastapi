from fastapi import APIRouter,Depends,Header,HTTPException,Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import crud
from starlette import status

from config.db_config import get_db
from models.users import User
from schemas.users import (LoginRequest, RegisterRequest, UserAuthResponse, UserInfoResponse,
                           UserUpdateRequest, UserUpdatePassword)
from crud import users
from utils.auth import get_current_user, parse_token
from utils.response import success_response

router = APIRouter(prefix="/api/user",tags=["users"])

@router.post("/register")
async def register(user_data: RegisterRequest,db: AsyncSession = Depends(get_db)):
    existing_user = await users.get_user_by_username(db, user_data.username)
    if existing_user:
        raise HTTPException(status_code=400, detail="用户已存在")
    user = await users.create_user(db, user_data)
    token = await users.create_token(db, user.id)
    # return {
    #     "code": 200,
    #     "message": "user registered",
    #     "data": {
    #         "token": token,
    #         "username": {
    #             "id": user.id,
    #             "username": user.username,
    #             "bio": user.bio,
    #             "avatar": user.avatar
    #         }
    #     }
    result_data = UserAuthResponse(token=token,userInfo=UserInfoResponse.model_validate(user))
    return success_response(message="注册成功",data=result_data)

@router.post("/login")
async def login(user_data: LoginRequest,db: AsyncSession = Depends(get_db)):
    user = await users.get_user(db, user_data.username,user_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="用户名或密码错误")
    token = await users.create_token(db, user.id)
    response_user = UserAuthResponse(token=token,userInfo=UserInfoResponse.model_validate(user))
    return success_response("登录成功",data=response_user)

@router.get("/info")
async def get_user_info(user: User = Depends(get_current_user)):
    return success_response("获取用户信息成功",UserInfoResponse.model_validate(user))

@router.put("/update")
async def update_user_info(user_data: UserUpdateRequest,user: User = Depends(get_current_user),db: AsyncSession = Depends(get_db)):
    updated_user = await users.update_user(db, user.username, user_data)
    return success_response("修改用户信息成功",updated_user)

@router.put("/password")
async def update_user_password(
        user_data: UserUpdatePassword,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    success = await users.update_password(db, user,user_data.new_password,user_data.old_password,)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="原密码不正确")
    return success_response("密码修改成功")


@router.post("/logout")
async def logout(
        authorization: str = Header(...,alias="Authorization"),
        db: AsyncSession = Depends(get_db)
):
    await users.delete_token(db, parse_token(authorization))
    return success_response("已退出登录")