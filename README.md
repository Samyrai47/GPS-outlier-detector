# Траектория - детектор выбросов в GPS-треках.

Это сервис для детекции выбрсов за счет алгоритмов машинного обучения: HDBSCAN, LOF, Isolation Forest.

## Траектория работы:

- Перейти на outlier-detector.online или поднять приложение локально.
- Загрузить файл с gps-треками в .pkl формате, в котором есть колонки [lat, lon, dt].
- Подождать результат анализа.
- Получить визуализацию размеченных данных с возможностью скачать размеченный .pkl файл.

## Стек:

- Java 21 JDK
- Spring Boot 4.0.6
- Python 3.12 (библиотеки, использованные для анализа см. в [requirements.txt](python/requirements.txt))
- Docker + Docker compose
- HTML + CSS (+ Thymeleaf)
- JS

Java + Spring - backend часть приложения.  
Python - скрипт для анализа GPS-треков.  
HTML + CSS + JS (+ Thymeleaf) - frontend часть приложения.  
Docker - развертывание приложения.

## Техническое устройство сервиса:

После передачи файла через endpoint в [AnalysisController](src/main/java/mipt/app/outlierdetector/controller/AnalysisController.java) запрос передается в 
[PythonScriptService](src/main/java/mipt/app/outlierdetector/service/PythonScriptService.java), где происходит запуск скрипта [detector.py](python/detector.py) для анализа траектории.
После завершения работы скрипта получаем geojson и .pkl файл. Первый используется для отрисовки данных на карте, второй можно скачать для дальнейшего использования.  

Для ознакомления с принципом анализа можно посмотреть [вот этот блокнот](https://colab.research.google.com/drive/1V1NL_SbtViEoKN9RLoA4K83weLIFILtX?usp=sharing).

## Развертывание

1) Убедиться, что на машине стоит docker.io, docker-compose-pluginm git
2) Выполнить ```git clone https://github.com/Samyrai47/GPS-outlier-detector.git```
3) Выполнить ```cd GPS-outlier-detector```
4) Выполнить ```docker compose up -d --build```
5) Для проверки статуса выполнить ```docker compose ps```
