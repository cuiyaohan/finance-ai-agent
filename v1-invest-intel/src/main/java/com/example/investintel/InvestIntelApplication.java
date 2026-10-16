package com.example.investintel;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * 投研情报 Agent · Java 私有化版入口。
 *
 * 说明：抓取→清洗→摘要→成简报；数值与事实只来自抓取原文，模型只做摘要与打标；
 * 所有输出末尾强制附加免责声明；密钥只从环境变量读取。
 */
@SpringBootApplication
public class InvestIntelApplication {

    public static void main(String[] args) {
        SpringApplication.run(InvestIntelApplication.class, args);
    }
}
