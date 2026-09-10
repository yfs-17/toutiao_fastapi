import { defineStore } from 'pinia';
import request from '../utils/request';

export const useUserStore = defineStore('user', {
  state: () => ({
    userInfo: null,
    token: '',
    isLogin: false,
    userBio: '这是我的个人简介'
  }),

  getters: {
    getUserInfo: (state) => state.userInfo,
    getToken: (state) => state.token,
    getLoginStatus: (state) => state.isLogin,
    getUserBio: (state) => state.userInfo?.bio || state.userBio
  },

  actions: {
    async login(userData) {
      try {
        const response = await request.post('/api/user/login', {
          username: userData.username,
          password: userData.password
        });

        if (response.data && response.data.code === 200) {
          this.userInfo = response.data.data.userInfo;
          this.token = response.data.data.token;
          this.isLogin = true;
          return { success: true, message: '登录成功' };
        }
        return { success: false, message: response.data.message || '登录失败' };
      } catch (error) {
        console.error('登录请求失败:', error);
        return { success: false, message: error.message || '登录请求失败，请稍后再试' };
      }
    },

    async register(userData) {
      try {
        const response = await request.post('/api/user/register', {
          username: userData.username,
          password: userData.password
        });

        if (response.data && response.data.code === 200) {
          this.userInfo = response.data.data.userInfo;
          this.token = response.data.data.token;
          this.isLogin = true;
          return { success: true, message: '注册成功' };
        }
        return { success: false, message: response.data.message || '注册失败' };
      } catch (error) {
        console.error('注册请求失败:', error);
        return { success: false, message: error.message || '注册请求失败，请稍后再试' };
      }
    },

    // 退出登录：通知后端作废 token，再清本地状态
    async logout() {
      if (this.token) {
        try {
          await request.post('/api/user/logout');
        } catch (error) {
          console.error('退出登录请求失败:', error);
        }
      }
      this.userInfo = null;
      this.token = '';
      this.isLogin = false;
    },

    // 获取用户信息
    async getUserInfoDetail() {
      if (!this.token) {
        return { success: false, message: '未登录' };
      }
      try {
        const response = await request.get('/api/user/info');

        if (response.data && response.data.code === 200) {
          this.userInfo = response.data.data;
          return { success: true, message: '获取用户信息成功', data: response.data.data };
        }
        return { success: false, message: response.data.message || '获取用户信息失败' };
      } catch (error) {
        console.error('获取用户信息请求失败:', error);
        return { success: false, message: error.message || '获取用户信息请求失败，请稍后再试' };
      }
    },

    // 更新个人简介
    async updateUserBio(bio) {
      if (!this.token) {
        return { success: false, message: '未登录' };
      }
      try {
        const response = await request.put('/api/user/update', { bio });

        if (response.data && response.data.code === 200) {
          if (this.userInfo) {
            this.userInfo.bio = bio;
          }
          return { success: true, message: '更新个人简介成功' };
        }
        return { success: false, message: response.data.message || '更新个人简介失败' };
      } catch (error) {
        console.error('更新个人简介请求失败:', error);
        return { success: false, message: error.message || '更新个人简介请求失败，请稍后再试' };
      }
    },

    // 修改密码（成功后后端会作废登录态，需要重新登录）
    async updatePassword(oldPassword, newPassword) {
      if (!this.token) {
        return { success: false, message: '未登录' };
      }
      try {
        const response = await request.put('/api/user/password', {
          oldPassword,
          newPassword
        });

        if (response.data && response.data.code === 200) {
          return { success: true, message: '密码修改成功' };
        }
        return { success: false, message: response.data.message || '密码修改失败' };
      } catch (error) {
        console.error('修改密码请求失败:', error);
        return { success: false, message: error.message || '修改密码请求失败，请稍后再试' };
      }
    }
  },

  // 持久化配置（pinia-plugin-persistedstate v4 语法）
  persist: {
    key: 'user-store',
    storage: localStorage
  }
});
