FROM python:latest
WORKDIR /root
COPY . /root/
RUN pip install fabric && pip install requests && pip install flask
CMD [ "python", "server.py", "2", "30" ]
