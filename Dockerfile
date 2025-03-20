FROM python:3.10-alpine

LABEL maintainer="Brodie Davis <brodie@malteksolutions.com>"

WORKDIR /src
RUN pip install --upgrade pip && pip install "poetry"

ENV ENV=dev
ENV PYTHONPATH=/src

COPY ./poetry.lock ./pyproject.toml /src/

COPY scripts /src/scripts
COPY migrations /src/migrations
COPY alembic.ini /src/alembic.ini
COPY one_request /src/one_request
COPY build /src/build

RUN poetry config virtualenvs.create false
RUN poetry install --only main

RUN addgroup -S one-request && \
    adduser -S one-request -G one-request
USER one-request

EXPOSE 8000

ENTRYPOINT ["/src/scripts/entry-point.sh"]
