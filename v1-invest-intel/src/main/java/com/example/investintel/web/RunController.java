package com.example.investintel.web;

import java.util.Map;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;

import com.example.investintel.service.BriefService;

/** POST /run 触发「抓取→清洗→摘要→成简报」流程；GET /latest 读取最近一次简报。 */
@RestController
public class RunController {

    private final BriefService briefService;

    public RunController(BriefService briefService) {
        this.briefService = briefService;
    }

    @PostMapping("/run")
    public Map<String, Object> run() {
        return briefService.run();
    }

    @GetMapping(value = "/latest", produces = "text/plain;charset=UTF-8")
    public String latest() {
        return briefService.run().get("content").toString();
    }
}
