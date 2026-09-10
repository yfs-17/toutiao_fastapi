import axios from 'axios';
import { apiConfig } from '../config/api';

// 与 store/user.js 里 persist 配置的 key 保持一致
const USER_STORE_KEY = 'user-store';

// 从持久化的登录态里取 token，避免和 store 形成循环依赖
function readToken() {
  try {
    const raw = localStorage.getItem(USER_STORE_KEY);
    return raw ? JSON.parse(raw).token || '' : '';
  } catch (error) {
    return '';
  }
}

const request = axios.create({
  baseURL: apiConfig.baseURL,
  timeout: 30000,
});

// 自动带上 token，调用方不用再手写 headers
request.interceptors.request.use((config) => {
  const token = readToken();
  if (token) {
    config.headers.Authorization = token;
  }
  return config;
});

// 统一处理登录失效和错误提示
request.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem(USER_STORE_KEY);
      if (!window.location.pathname.startsWith('/login')) {
        window.location.href = '/login';
      }
    }
    error.message = error.response?.data?.message || error.message || '网络请求失败';
    return Promise.reject(error);
  }
);

export default request;
