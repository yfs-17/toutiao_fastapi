from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, max_length=50, description="密码")

class UserInfoBase(BaseModel):
     """
     ⽤户信息基础数据模型
     """
     nickname: Optional[str] = Field(None, max_length=50, description="昵称")
     avatar: Optional[str] = Field(None, max_length=255, description="头像URL")
     gender: Optional[str] = Field(None, max_length=10, description="性别")
     bio: Optional[str] = Field(None, max_length=500, description="个⼈简介")

class UserInfoResponse(UserInfoBase):
    id: int
    username: str

    model_config = ConfigDict(
        from_attributes=True
    )



class UserAuthResponse(BaseModel):
    token: str
    user_info: UserInfoResponse = Field(...,alias = "userInfo")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )

class UserUpdateRequest(BaseModel):
    nickname: Optional[str] = None
    avatar: Optional[str] = None
    gender: Optional[str] = None
    bio: Optional[str] = None
    phone: Optional[str] = None

class UserUpdatePassword(BaseModel):
    old_password: str = Field(...,alias="oldPassword",description="旧密码")
    new_password: str = Field(...,min_length=6,alias="newPassword")