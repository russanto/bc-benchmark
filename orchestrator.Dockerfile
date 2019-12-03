FROM python:latest
RUN mkdir /sdk /app
COPY ./sdk/ /sdk/
COPY ./orchestrator/ /app/
RUN pip install -e /sdk
WORKDIR /app
RUN pip install -r requirements.txt
CMD [ "python", "main.py" ]
