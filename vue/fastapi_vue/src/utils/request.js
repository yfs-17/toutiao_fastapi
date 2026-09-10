import axios from 'axios';
import { apiConfig } from '../config/api';
import { useUserStore } from '../store/user';

const request = axios.create({
  baseURL: apiConfig.baseURL,
  timeout: 30000,
});

// 自动带上 token，调用方不用再手写 headers。
// 直接读 pinia store，不依赖持久化插件的存储 key 和格式。
request.interceptors.request.use((config) => {
  try {
    const token = useUserStore().token;
    if (token) {
      config.headers.Authorization = token;
    }
  } catch (error) {
    // pinia 尚未就绪时忽略
  }
  return config;
});

// 统一处理登录失效和错误提示
request.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const url = error.config?.url || '';
    // 登录接口自身的 401 表示账号密码错误，不能当成登录态失效
    const isAuthEntry = url.includes('/api/user/login');

    if (status === 401 && !isAuthEntry) {
      try {
        useUserStore().$reset();
      } catch (e) {
        // pinia 尚未就绪时忽略
      }
      if (!window.location.pathname.startsWith('/login')) {
        sessionStorage.setItem('authExpired', '1');
        window.location.href = '/login';
      }
    }
    error.message = error.response?.data?.message || error.message || '网络请求失败';
    return Promise.reject(error);
  }
);

export default request;
