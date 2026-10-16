# ---------- 阶段 1：构建 ----------
FROM maven:3.9-eclipse-temurin-17 AS build
WORKDIR /app
COPY pom.xml .
# 先只拷 pom 拉依赖，利用 Docker 层缓存
RUN mvn -q -B dependency:go-offline
COPY src ./src
RUN mvn -q -B clean package -DskipTests

# ---------- 阶段 2：运行 ----------
FROM eclipse-temurin:17-jre
WORKDIR /app
COPY --from=build /app/target/*.jar app.jar
# 密钥与地址通过环境变量注入，镜像内不落任何密钥
ENV SPRING_AI_OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4 \
    SPRING_AI_OPENAI_MODEL=glm-4.5-flash
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
