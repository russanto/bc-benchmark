FROM python:latest
RUN apt-get update && apt-get install -y apt-transport-https ca-certificates curl gnupg2 software-properties-common
RUN curl -fsSL https://download.docker.com/linux/debian/gpg | apt-key add -
RUN add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/debian $(lsb_release -cs) stable"
RUN apt-get update && apt-get install -y docker-ce docker-ce-cli containerd.io
RUN mkdir /sdk /app
COPY ./sdk/ /sdk/
COPY ./resource_manager/host_manager/ /app/
RUN pip install -e /sdk
WORKDIR /app
RUN pip install -r requirements.txt
CMD [ "python", "main.py" ]
