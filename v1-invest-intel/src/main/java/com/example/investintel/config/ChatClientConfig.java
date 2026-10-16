package com.example.investintel.config;

import java.io.IOException;
import java.nio.charset.StandardCharsets;

import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.model.ChatModel;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.io.Resource;

/**
 * 构造带系统提示词的 ChatClient。
 * 系统提示词取自 resources/system-prompt.txt（内容复制自 _shared/system_prompt.txt），
 * 会话记忆由 MemoryStore 在调用侧注入，避免依赖不同版本的 Advisor API。
 */
@Configuration
public class ChatClientConfig {

    @Bean
    public ChatClient chatClient(ChatModel chatModel,
                                 @Value("classpath:system-prompt.txt") Resource systemPrompt) throws IOException {
        String sys = new String(systemPrompt.getInputStream().readAllBytes(), StandardCharsets.UTF_8).trim();
        return ChatClient.builder(chatModel)
                .defaultSystem(sys)
                .build();
    }
}
