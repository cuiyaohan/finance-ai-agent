package com.example.investintel.service;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardOpenOption;
import java.util.Map;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import com.fasterxml.jackson.databind.ObjectMapper;

/** 每次调用写一条 trace（时间/耗时/token 等）到 logs/trace.jsonl。 */
@Service
public class TraceService {

    private final Path traceFile;
    private final ObjectMapper mapper = new ObjectMapper();

    public TraceService(@Value("${app.storage.trace-file:logs/trace.jsonl}") String tracePath) {
        this.traceFile = Paths.get(tracePath);
    }

    public synchronized void append(Map<String, Object> row) {
        try {
            Path parent = traceFile.toAbsolutePath().getParent();
            if (parent != null) {
                Files.createDirectories(parent);
            }
            String line = mapper.writeValueAsString(row) + System.lineSeparator();
            Files.writeString(traceFile, line, StandardOpenOption.CREATE, StandardOpenOption.APPEND);
        } catch (IOException ignored) {
            // trace 失败不影响主流程
        }
    }

    public Path file() {
        return traceFile;
    }
}
