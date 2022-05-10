FROM python:3.11.0b1-alpine3.15

RUN /sbin/apk add --no-cache libpq
RUN /usr/sbin/adduser -g python -D python

USER python
RUN /usr/local/bin/python -m venv /home/python/venv

COPY --chown=python:python requirements.txt /home/python/lessonly-api/requirements.txt
RUN /home/python/venv/bin/pip install --no-cache-dir --requirement /home/python/lessonly-api/requirements.txt

COPY --chown=python:python lessonly.py /home/python/lessonly-api/lessonly.py
COPY --chown=python:python get-assignment-data.py /home/python/lessonly-api/get-assignment-data.py
COPY --chown=python:python get-learning-content.py /home/python/lessonly-api/get-learning-content.py
COPY --chown=python:python get-user-data.py /home/python/lessonly-api/get-user-data.py

ENV PATH="/home/python/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE="1" \
    PYTHONUNBUFFERED="1" \
    TZ="Etc/UTC"

LABEL org.opencontainers.image.authors="William Jackson <wjackson@informatica.com>" \
      org.opencontainers.image.source="https://github.com/informatica-na-presales-ops/lessonly-api"
