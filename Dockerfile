FROM maven:3.9-eclipse-temurin-21 AS build

WORKDIR /build

COPY pom.xml .
COPY src ./src

RUN mvn clean package -DskipTests


FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y openjdk-21-jre-headless && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=build /build/target/*.jar app.jar

COPY python /app/python

RUN python -m venv /app/venv
RUN /app/venv/bin/pip install --upgrade pip
RUN /app/venv/bin/pip install --no-cache-dir -r /app/python/requirements.txt

RUN mkdir -p /app/workdir

ENV APP_PYTHON_EXECUTABLE=/app/venv/bin/python
ENV APP_PYTHON_SCRIPT_PATH=/app/python/detector.py
ENV APP_ANALYSIS_WORKDIR=/app/workdir

EXPOSE 8080

CMD ["java", "-jar", "app.jar"]