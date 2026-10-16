package com.example.investintel.service;

import java.io.IOException;
import java.nio.charset.StandardCharsets;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.Resource;
import org.springframework.stereotype.Service;

/** 加载并强制附加免责声明（resources/disclaimer.txt）。 */
@Service
public class DisclaimerService {

    private final String text;

    public DisclaimerService(@Value("classpath:disclaimer.txt") Resource resource) throws IOException {
        this.text = new String(resource.getInputStream().readAllBytes(), StandardCharsets.UTF_8).trim();
    }

    public String text() {
        return text;
    }

    /** 把免责声明追加到正文末尾，保证所有对外输出都带合规声明。 */
    public String appendTo(String body) {
        String b = body == null ? "" : body.strip();
        return b + "\n\n---\n" + text + "\n";
    }
}
