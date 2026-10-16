package com.example.investintel.service;

import java.util.ArrayDeque;
import java.util.Deque;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

import org.springframework.stereotype.Component;

/** 极简会话记忆：按 session 保留最近 N 轮对话，供调用侧拼进提示词。 */
@Component
public class MemoryStore {

    private static final int MAX_MESSAGES = 6;
    private final Map<String, Deque<String>> store = new ConcurrentHashMap<>();

    public void add(String session, String message) {
        Deque<String> deque = store.computeIfAbsent(session, k -> new ArrayDeque<>());
        synchronized (deque) {
            deque.addLast(message);
            while (deque.size() > MAX_MESSAGES) {
                deque.removeFirst();
            }
        }
    }

    public String historyBlock(String session) {
        Deque<String> deque = store.get(session);
        if (deque == null || deque.isEmpty()) {
            return "";
        }
        synchronized (deque) {
            return String.join("\n", deque);
        }
    }
}
