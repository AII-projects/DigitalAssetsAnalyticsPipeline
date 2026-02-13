FROM spark:3.5.7-java17-python3

USER root
WORKDIR /opt/spark-app

COPY requirements.txt /opt/spark-app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . /opt/spark-app

USER spark
