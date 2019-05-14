FROM python:latest
RUN apt-get update && apt-get install -y apt-transport-https ca-certificates curl gnupg2 software-properties-common
RUN curl -fsSL https://download.docker.com/linux/debian/gpg | apt-key add -
RUN add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/debian $(lsb_release -cs) stable"
RUN apt-get update && apt-get install -y docker-ce-cli
RUN mkdir /controller
WORKDIR /controller
COPY . /controller/
RUN pip install -r requirements.txt
ENV RUNNING_IN_CONTAINER=1
CMD [ "python", "server.py" ]
