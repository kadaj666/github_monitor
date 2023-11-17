FROM python:3.9

COPY . /opt/monitoring
WORKDIR /opt/monitoring
RUN pip3 install -r /opt/monitoring/requirements.txt
CMD ["python", "/opt/monitoring/github_monitoring.py", "--config", "/opt/monitoring/config.json"]
