<template>
  <div class="ai-chat-container">
    <van-nav-bar title="AI问答" fixed>
      <template #right>
        <van-icon name="wap-nav" size="20" @click="openSessions" />
      </template>
    </van-nav-bar>

    <!-- 会话列表抽屉 -->
    <van-popup
      v-model:show="showSessions"
      position="left"
      :style="{ width: '78%', height: '100%' }"
    >
      <div class="session-panel">
        <div class="session-header">
          <span>对话记录</span>
          <van-icon name="cross" @click="showSessions = false" />
        </div>
        <van-button
          block
          type="primary"
          icon="plus"
          size="small"
          :disabled="streaming"
          @click="onNewSession"
        >
          新建对话
        </van-button>
        <div class="session-list">
          <div
            v-for="item in conversations"
            :key="item.id"
            :class="['session-item', { active: item.id === currentId }]"
            @click="onSelectSession(item.id)"
          >
            <span class="session-title">{{ item.title }}</span>
            <van-icon name="delete-o" class="session-del" @click.stop="onDeleteSession(item)" />
          </div>
          <van-empty v-if="!conversations.length" description="还没有对话" />
        </div>
      </div>
    </van-popup>

    <div class="chat-content">
      <div class="messages-container" ref="messagesContainer">
        <div v-if="!messages.length" class="welcome">
          <p>你好，我是新闻助手。</p>
          <p>可以帮你查新闻、搜关键词、管理收藏和浏览历史。</p>
          <p>试试问我："有哪些新闻分类？"</p>
        </div>

        <div
          v-for="(message, index) in messages"
          :key="index"
          :class="['message', message.role === 'user' ? 'user-message' : 'ai-message',
                   { 'has-cards': message.cards && message.cards.length }]"
        >
          <div class="message-content">
            <div
              v-if="message.role === 'assistant' && message.content === '' && streaming && index === messages.length - 1"
              class="typing-indicator"
            >
              <span></span><span></span><span></span>
            </div>
            <div v-else v-html="formatMessage(message.content)"></div>
          </div>
          <div v-if="message.cards && message.cards.length" class="news-cards">
            <news-item v-for="item in message.cards" :key="item.id" :news="item" />
          </div>
        </div>

        <div v-if="statusText" class="status-hint">{{ statusText }}</div>

        <div v-if="pendingInterrupt" class="confirm-card">
          <div class="confirm-text">{{ pendingInterrupt.question }}</div>
          <div class="confirm-actions">
            <van-button size="small" :disabled="streaming" @click="onAnswer(false)">取消</van-button>
            <van-button size="small" type="danger" :disabled="streaming" @click="onAnswer(true)">
              确认
            </van-button>
          </div>
        </div>
      </div>

      <div class="input-container">
        <van-field
          v-model="userInput"
          rows="1"
          autosize
          type="textarea"
          placeholder="请输入问题..."
          class="chat-input"
          :disabled="streaming || !!pendingInterrupt"
          @keypress.enter.prevent="sendMessage"
        />
        <van-button
          type="primary"
          class="send-button"
          :disabled="streaming || !!pendingInterrupt || !userInput.trim()"
          @click="sendMessage"
        >
          发送
        </van-button>
      </div>
    </div>

    <tab-bar />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue';
import { useRouter } from 'vue-router';
import { showToast, showDialog } from 'vant';
import * as marked from 'marked';
import DOMPurify from 'dompurify';
import TabBar from '../components/TabBar.vue';
import NewsItem from '../components/NewsItem.vue';
import { useChatStore } from '../store/modules/chat';
import { useUserStore } from '../store/user';

const router = useRouter();
const chatStore = useChatStore();
const userStore = useUserStore();

const userInput = ref('');
const showSessions = ref(false);
const messagesContainer = ref(null);

const messages = computed(() => chatStore.messages);
const conversations = computed(() => chatStore.conversations);
const currentId = computed(() => chatStore.currentId);
const streaming = computed(() => chatStore.streaming);
const statusText = computed(() => chatStore.statusText);
const pendingInterrupt = computed(() => chatStore.pendingInterrupt);

const formatMessage = (content) => {
  if (!content) return '';
  return DOMPurify.sanitize(marked.parse(content));
};

const scrollToBottom = () => {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
  }
};

const sendMessage = async () => {
  const text = userInput.value.trim();
  if (!text || streaming.value || pendingInterrupt.value) return;
  userInput.value = '';
  await chatStore.sendMessage(text);
};

const onAnswer = async (confirmed) => {
  await chatStore.answerInterrupt(confirmed);
};

const openSessions = () => {
  showSessions.value = true;
};

const onNewSession = async () => {
  if (streaming.value) return;
  showSessions.value = false;
  try {
    await chatStore.createConversation();
  } catch (error) {
    showToast('新建对话失败');
  }
};

const onSelectSession = async (id) => {
  if (id === currentId.value || streaming.value) {
    showSessions.value = false;
    return;
  }
  showSessions.value = false;
  await chatStore.openConversation(id);
};

const onDeleteSession = async (item) => {
  try {
    await showDialog({
      title: '删除对话',
      message: `确定删除「${item.title}」吗？删除后无法恢复。`,
      showCancelButton: true,
    });
  } catch {
    return;
  }
  try {
    await chatStore.deleteConversation(item.id);
    showToast('已删除');
  } catch (error) {
    showToast('删除失败');
  }
};

watch(messages, () => nextTick(scrollToBottom), { deep: true });
watch(statusText, () => nextTick(scrollToBottom));
watch(pendingInterrupt, () => nextTick(scrollToBottom));

onMounted(async () => {
  if (!userStore.getLoginStatus) {
    showToast('请先登录');
    router.replace('/login');
    return;
  }
  await chatStore.loadConversations();
  if (chatStore.conversations.length) {
    await chatStore.openConversation(chatStore.conversations[0].id);
  }
  scrollToBottom();
});
</script>

<style scoped>
.ai-chat-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  padding-top: 46px;
  padding-bottom: 50px;
  box-sizing: border-box;
}

.chat-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
}

.welcome {
  color: #969799;
  font-size: 14px;
  line-height: 1.9;
  padding: 20px 6px;
}

.welcome p {
  margin: 4px 0;
}

.message {
  margin-bottom: 10px;
  max-width: 82%;
}

.user-message {
  margin-left: auto;
}

.ai-message {
  margin-right: auto;
}

.message-content {
  padding: 10px;
  border-radius: 10px;
  word-break: break-word;
  font-size: 14px;
  line-height: 1.6;
}

.user-message .message-content {
  background-color: #007aff;
  color: white;
}

.ai-message .message-content {
  background-color: #f2f2f2;
  color: #333;
}

/* 带新闻卡片的消息占满整行 */
.message.has-cards {
  max-width: 100%;
  width: 100%;
}

.news-cards {
  margin-top: 8px;
  border: 1px solid #ececec;
  border-radius: 8px;
  overflow: hidden;
  background-color: #fff;
}

.news-cards :deep(.news-item:last-child) {
  border-bottom: none;
}

.status-hint {
  font-size: 12px;
  color: #969799;
  padding: 2px 6px 8px;
}

.confirm-card {
  background: #fff7e6;
  border: 1px solid #ffd591;
  border-radius: 8px;
  padding: 12px;
  margin: 6px 0 12px;
}

.confirm-text {
  font-size: 14px;
  color: #874d00;
  margin-bottom: 10px;
  line-height: 1.5;
}

.confirm-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

.input-container {
  display: flex;
  padding: 10px;
  border-top: 1px solid #eee;
  background-color: #fff;
}

.chat-input {
  flex: 1;
  margin-right: 10px;
}

.send-button {
  align-self: flex-end;
}

/* 会话抽屉 */
.session-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 12px;
  box-sizing: border-box;
}

.session-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 12px;
}

.session-list {
  flex: 1;
  overflow-y: auto;
  margin-top: 10px;
}

.session-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 11px 10px;
  border-radius: 8px;
  font-size: 14px;
  color: #323233;
  margin-bottom: 4px;
}

.session-item.active {
  background-color: #e8f3ff;
  color: #1989fa;
}

.session-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-right: 8px;
}

.session-del {
  color: #c8c9cc;
  padding: 4px;
}

/* 打字指示器 */
.typing-indicator {
  display: flex;
  padding: 5px;
}

.typing-indicator span {
  height: 8px;
  width: 8px;
  background-color: #999;
  border-radius: 50%;
  margin: 0 2px;
  display: inline-block;
  animation: bounce 1.5s infinite ease-in-out;
}

.typing-indicator span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-indicator span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes bounce {
  0%, 60%, 100% {
    transform: translateY(0);
  }
  30% {
    transform: translateY(-5px);
  }
}

/* Markdown 样式 */
:deep(pre) {
  background-color: #f0f0f0;
  padding: 10px;
  border-radius: 4px;
  overflow-x: auto;
}

:deep(code) {
  font-family: monospace;
  background-color: #f0f0f0;
  padding: 2px 4px;
  border-radius: 4px;
}

:deep(p) {
  margin: 8px 0;
}

:deep(ul), :deep(ol) {
  padding-left: 20px;
}

:deep(a) {
  color: #1989fa;
  text-decoration: none;
}
</style>
