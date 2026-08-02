FROM python:3.12-slim
WORKDIR /app
COPY server.py styles.css app.js front.html back.html login.html watering.html ./
EXPOSE 8765
CMD ["python3", "server.py"]
