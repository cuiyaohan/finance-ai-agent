package com.example.investintel.web;

import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.util.LinkedHashMap;
import java.util.Map;

import org.springframework.ai.chat.client.ChatClient;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import com.example.investintel.service.DisclaimerService;
import com.example.investintel.service.MemoryStore;
import com.example.investintel.service.TraceService;

/** GET /chat?msg= 返回模型回复（末尾强制附加免责声明，含会话记忆）。 */
@RestController
public class ChatController {

    private static final ZoneId CST = ZoneId.of("Asia/Shanghai");

    private final ChatClient chatClient;
    private final DisclaimerService disclaimer;
    private final MemoryStore memory;
    private final TraceService trace;
    private final String model;

    public ChatController(ChatClient chatClient, DisclaimerService disclaimer, MemoryStore memory,
                          TraceService trace,
                          @Value("${spring.ai.openai.chat.options.model:glm-4.5-flash}") String model) {
        this.chatClient = chatClient;
        this.disclaimer = disclaimer;
        this.memory = memory;
        this.trace = trace;
        this.model = model;
    }

    @GetMapping(value = "/chat", produces = "text/plain;charset=UTF-8")
    public String chat(@RequestParam("msg") String msg,
                       @RequestParam(value = "session", defaultValue = "default") String session) {
        long start = System.currentTimeMillis();
        try {
            String history = memory.historyBlock(session);
            String prompt = history.isEmpty() ? msg : ("已有对话历史：\n" + history + "\n\n用户：" + msg);
            String reply = chatClient.prompt().user(prompt).call().content();
            if (reply == null || reply.isBlank()) {
                reply = "（模型未返回内容）";
            } else {
                reply = reply.strip();
            }
            memory.add(session, "用户：" + msg);
            memory.add(session, "助理：" + reply);

            String out = disclaimer.appendTo(reply);

            Map<String, Object> row = new LinkedHashMap<>();
            row.put("ts", OffsetDateTime.now(CST).toString());
            row.put("endpoint", "/chat");
            row.put("session", session);
            row.put("model", model);
            row.put("msg_chars", msg.length());
            row.put("reply_chars", out.length());
            row.put("elapsed_ms", System.currentTimeMillis() - start);
            row.put("has_disclaimer", out.contains("仅供参考，不构成投资建议"));
            trace.append(row);

            return out;
        } catch (Exception e) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "模型调用失败：" + e.getMessage());
        }
    }

    @GetMapping("/health")
    public Map<String, Object> health() {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("status", "ok");
        m.put("model", model);
        m.put("disclaimer_loaded", !disclaimer.text().isBlank());
        return m;
    }
}
