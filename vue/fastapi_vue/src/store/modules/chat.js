import { defineStore } from 'pinia';
import { useUserStore } from '../user';
import { apiConfig } from '../../config/api';
import request from '../../utils/request';

// 工具名 -> 界面提示语
const TOOL_LABELS = {
  get_news_categories: '正在获取新闻分类…',
  get_news_list: '正在查询新闻列表…',
  get_news_detail: '正在读取新闻详情…',
  search_news: '正在搜索新闻…',
  list_my_favorites: '正在读取你的收藏…',
  add_favorite: '正在添加收藏…',
  remove_favorite: '正在取消收藏…',
  list_my_history: '正在读取浏览历史…',
  delete_history_item: '正在删除浏览记录…',
  clear_history: '正在清空浏览历史…',
  clear_favorites: '正在清空收藏…',
};

// 解析一个 SSE 数据块
function parseSSE(block) {
  let event = 'message';
  let data = '';
  for (const line of block.split('\n')) {
    if (line.startsWith('event: ')) event = line.slice(7).trim();
    else if (line.startsWith('data: ')) data += line.slice(6);
  }
  let payload = {};
  if (data) {
    try {
      payload = JSON.parse(data);
    } catch (e) {
      payload = {};
    }
  }
  return { event, payload };
}

export const useChatStore = defineStore('chat', {
  state: () => ({
    conversations: [],
    currentId: null,
    messages: [],           // { role: 'user' | 'assistant', content: string }
    streaming: false,
    loadingConversations: false,
    statusText: '',         // 工具执行时的提示
    pendingInterrupt: null, // { question, action }
  }),

  getters: {
    getConversations: (state) => state.conversations,
    getMessages: (state) => state.messages,
    getCurrentId: (state) => state.currentId,
    isStreaming: (state) => state.streaming,
    getStatusText: (state) => state.statusText,
    getPendingInterrupt: (state) => state.pendingInterrupt,
  },

  actions: {
    _headers() {
      const userStore = useUserStore();
      return { Authorization: userStore.token };
    },

    // 拉取会话列表
    async loadConversations() {
      this.loadingConversations = true;
      try {
        const res = await request.get('/api/ai/conversations');
        if (res.data.code === 200) {
          this.conversations = res.data.data;
        }
      } catch (error) {
        console.error('获取会话列表失败:', error);
      } finally {
        this.loadingConversations = false;
      }
    },

    // 新建会话
    async createConversation() {
      const res = await request.post('/api/ai/conversations', {});
      const conversation = res.data.data;
      this.conversations.unshift(conversation);
      this.currentId = conversation.id;
      this.messages = [];
      this.pendingInterrupt = null;
      return conversation;
    },

    // 切换会话，读取历史消息
    async openConversation(id) {
      this.currentId = id;
      this.messages = [];
      this.pendingInterrupt = null;
      try {
        const res = await request.get(`/api/ai/conversations/${id}/messages`);
        if (res.data.code === 200) {
          this.messages = res.data.data;
        }
      } catch (error) {
        console.error('读取会话记录失败:', error);
      }
    },

    // 删除会话
    async deleteConversation(id) {
      await request.delete(`/api/ai/conversations/${id}`);
      this.conversations = this.conversations.filter((item) => item.id !== id);
      if (this.currentId === id) {
        this.currentId = null;
        this.messages = [];
        this.pendingInterrupt = null;
      }
    },

    // 发送消息
    async sendMessage(text) {
      if (!text || this.streaming) return;
      if (!this.currentId) {
        await this.createConversation();
      }
      this.messages.push({ role: 'user', content: text });
      this.messages.push({ role: 'assistant', content: '', cards: [] });
      await this._run({ conversationId: this.currentId, message: text });
    },

    // 回应 interrupt 确认框
    async answerInterrupt(confirmed) {
      if (!this.pendingInterrupt || this.streaming) return;
      this.messages.push({ role: 'user', content: confirmed ? '确认' : '取消' });
      this.messages.push({ role: 'assistant', content: '', cards: [] });
      this.pendingInterrupt = null;
      await this._run({ conversationId: this.currentId, resume: confirmed });
    },

    // 核心：发起 SSE 请求并消费事件流
    async _run(body) {
      this.streaming = true;
      this.statusText = '';
      const assistant = this.messages[this.messages.length - 1];
      try {
        const response = await fetch(`${apiConfig.baseURL}/api/ai/chat`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...this._headers(),
          },
          body: JSON.stringify(body),
        });
        if (response.status === 401) {
          localStorage.removeItem('user-store');
          window.location.href = '/login';
          throw new Error('登录已失效');
        }
        if (!response.ok) {
          throw new Error(`请求失败 (${response.status})`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const blocks = buffer.split('\n\n');
          buffer = blocks.pop() || '';

          for (const block of blocks) {
            if (!block.trim()) continue;
            const { event, payload } = parseSSE(block);
            if (event === 'token') {
              assistant.content += payload.text || '';
              this.statusText = '';
            } else if (event === 'tool_start') {
              this.statusText = TOOL_LABELS[payload.name] || '正在处理…';
            } else if (event === 'tool_end') {
              this.statusText = '';
            } else if (event === 'news') {
              // 工具旁路推来的新闻卡片，挂在当前这条回复下面
              if (!assistant.cards) assistant.cards = [];
              assistant.cards.push(payload);
            } else if (event === 'interrupt') {
              this.pendingInterrupt = {
                question: payload.question,
                action: payload.action,
              };
            } else if (event === 'error') {
              throw new Error(payload.message || '服务端出错');
            }
          }
        }

        if (!assistant.content && !this.pendingInterrupt) {
          assistant.content = '抱歉，我没有生成回复，请再试一次。';
        }
      } catch (error) {
        console.error('AI 请求失败:', error);
        assistant.content = assistant.content || `出错了：${error.message}`;
      } finally {
        this.streaming = false;
        this.statusText = '';
      }
    },
  },
});
