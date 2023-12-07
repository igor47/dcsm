FROM python:3.12.0-alpine3.18
RUN apk add --no-cache age
WORKDIR /srv
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY dscn.py .
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s CMD python3 dscn.py
ENTRYPOINT ["python3", "dscn.py", "sleep"]

