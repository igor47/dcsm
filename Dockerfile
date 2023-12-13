FROM python:3.12.0-alpine3.18
RUN apk add --no-cache age
WORKDIR /srv
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY dcsm.py .
ENTRYPOINT ["python3", "dcsm.py"]
CMD ["run"]

